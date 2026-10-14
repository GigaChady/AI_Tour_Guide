package ai.tour.guide.domain.route

import ai.tour.guide.R
import ai.tour.guide.data.room.AppDatabase
import ai.tour.guide.data.room.entity.RouteStop
import ai.tour.guide.domain.AppEventBus
import ai.tour.guide.domain.AppEventBusEvent
import ai.tour.guide.domain.playback.NarrationPlayerHolder
import ai.tour.guide.domain.playback.NavigatingPlayer
import android.content.Context
import android.net.Uri
import android.os.SystemClock
import android.util.Log
import androidx.annotation.MainThread
import androidx.core.content.ContextCompat.getString
import androidx.core.net.toUri
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.koin.core.annotation.Singleton
import java.io.File

data class RoutePlaybackState(
    val positionMs: Long = 0L,
    val bufferedPositionMs: Long = 0L,
    val durationMs: Long = 0L,
    val isPlaying: Boolean = false,
    val isEnded: Boolean = false
)

data class RouteNavigationState(
    val currentStopId: Int? = null,
    val currentLatestStopId: Int? = null,
    val historyOffset: Int = 0,
    val totalStops: Int? = null,
    val pendingNextChunkRequestAfterStopId: Int? = null,
)

@OptIn(ExperimentalCoroutinesApi::class)
@Singleton
class RouteNarrationPlaybackService(
    private val context: Context,
    private val routeAudioRepository: RouteAudioRepository,
    private val eventBus: AppEventBus,
    private val playerHolder: NarrationPlayerHolder,
    private val routeService: RouteService,
    private val appDatabase: AppDatabase
) {
    private var player: ExoPlayer? = null
    private var progressJob: Job? = null
    private var navigationScope: CoroutineScope? = null
    private var hasBroadcastLocationNearCurrentNarrationEnd: Boolean = false
    private var autoPlayEnabled: Boolean = true
    private var lastPlayedStopId: Int? = null
    private var latestAvailableStopId: Int? = null
    private var requestedNarrationAfterStopId: Int? = null
    private var narrationRequestedAtMs: Long = 0L
    private val _isPlaying = MutableStateFlow(false)
    private val _playbackState = MutableStateFlow(RoutePlaybackState())
    private val _navigationState = MutableStateFlow(RouteNavigationState())

    val isPlayingFlow: StateFlow<Boolean> = _isPlaying.asStateFlow()
    val playbackStateFlow: StateFlow<RoutePlaybackState> = _playbackState.asStateFlow()
    val navigationStateFlow: StateFlow<RouteNavigationState> = _navigationState.asStateFlow()

    private val currentStopId = navigationStateFlow.map { it.currentStopId }.distinctUntilChanged()
    private val currentLatestStopId =
        navigationStateFlow.map { it.currentLatestStopId }.distinctUntilChanged()
    private val historyOffset = navigationStateFlow.map { it.historyOffset }.distinctUntilChanged()

    private val latestStopId: Flow<Int?> = routeService.currentSessionIdFlow.flatMapLatest { id ->
        appDatabase.routeStopDao().getLatestStopIdForServerSession(id)
    }

    private val selectedStopId: Flow<Int?> =
        combine(currentLatestStopId, historyOffset) { stopId, offset ->
            Pair(stopId, offset)
        }.flatMapLatest { (stopId, offset) ->
            appDatabase.routeStopDao().getStopIdByOffsetFromStop(stopId, offset)
        }

    private val currentStop: Flow<RouteStop?> = currentStopId.flatMapLatest { stopId ->
        appDatabase.routeStopDao().getStopById(stopId)
    }

    private suspend fun ensurePlayer() {
        withContext(Dispatchers.Main.immediate) {
            player = playerHolder.get()
            player?.addListener(playerListener)
            startProgressPolling()
        }
    }

    private fun startProgressPolling() {
        if (progressJob?.isActive == true) {
            return
        }
        progressJob = CoroutineScope(Dispatchers.Main.immediate).launch {
            while (isActive) {
                publishPlaybackState()
                delay(100L)
            }
        }
    }

    private fun publishPlaybackState() {
        val currentPlayer = player ?: run {
            _playbackState.value = RoutePlaybackState()
            return
        }

        val duration = when {
            currentPlayer.duration > 0L -> currentPlayer.duration
            else -> 0L
        }
        _playbackState.value = RoutePlaybackState(
            positionMs = currentPlayer.currentPosition.coerceAtLeast(0L),
            bufferedPositionMs = currentPlayer.bufferedPosition.coerceAtLeast(0L),
            durationMs = duration,
            isPlaying = currentPlayer.isPlaying,
            isEnded = currentPlayer.playbackState == Player.STATE_ENDED
        )
        maybeBroadcastLocationNearNarrationEnd(currentPlayer.currentPosition, duration)
    }

    private fun maybeBroadcastLocationNearNarrationEnd(positionMs: Long, durationMs: Long) {
        if (durationMs <= 0L || hasBroadcastLocationNearCurrentNarrationEnd) {
            return
        }

        val minPositionForNearEndBroadcast = when {
            durationMs <= NARRATION_END_LOCATION_BROADCAST_THRESHOLD_MS ->
                (durationMs * SHORT_NARRATION_END_BROADCAST_FRACTION).toLong()

            else -> durationMs - NARRATION_END_LOCATION_BROADCAST_THRESHOLD_MS
        }

        if (positionMs in minPositionForNearEndBroadcast..<durationMs) {
            hasBroadcastLocationNearCurrentNarrationEnd = true
            CoroutineScope(Dispatchers.IO).launch {
                eventBus.publish(AppEventBusEvent.AudioChunkNearlyFinished(positionMs))
            }
        }
    }

    suspend fun playAudioFile(
        filePath: String,
        title: String? = null,
        artist: String? = null,
        artworkUrl: String? = null,
        mediaId: String = MediaItem.DEFAULT_MEDIA_ID
    ) {
        withContext(Dispatchers.Main.immediate) {
            ensurePlayer()
            val currentPlayer = player ?: return@withContext

            val metadata = MediaMetadata.Builder()
                .setTitle(title ?: getString(context, R.string.audio_player_default_place_name))
                .setArtist(artist ?: getString(context, R.string.audio_player_desc))
                .apply { artworkUrl?.let { setArtworkUri(it.toUri()) } }
                .build()

            val item = MediaItem.Builder()
                .setMediaId(mediaId)
                .setUri(Uri.fromFile(File(filePath)))
                .setMediaMetadata(metadata)
                .build()

            hasBroadcastLocationNearCurrentNarrationEnd = false
            autoPlayEnabled = true
            currentPlayer.setMediaItem(item)
            currentPlayer.prepare()
            currentPlayer.play()
            publishPlaybackState()
        }
    }

    suspend fun playNarration() {
        withContext(Dispatchers.Main.immediate) {
            ensurePlayer()
            autoPlayEnabled = true
            player?.play()
            _isPlaying.value = player?.isPlaying == true
        }
    }

    suspend fun pauseNarration() {
        withContext(Dispatchers.Main.immediate) {
            autoPlayEnabled = false
            player?.pause()
            _isPlaying.value = false
        }
    }

    @MainThread
    fun startNavigation() {
        if (navigationScope?.isActive == true) {
            return
        }
        navigationScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate).apply {
            launch { trackCurrentLatestStop() }
            launch { syncCurrentStopWithSelectedStop() }
            launch { trackTotalStops() }
            launch { playCurrentStopAudio() }
            launch { listenForNarrationEvents() }
        }
    }

    @MainThread
    fun skipToNext() {
        val state = _navigationState.value
        if (state.historyOffset > 0) {
            _navigationState.update { it.copy(historyOffset = state.historyOffset - 1) }
            return
        }

        _navigationState.update {
            it.copy(pendingNextChunkRequestAfterStopId = state.currentLatestStopId)
        }
        requestNextNarration()
    }

    @MainThread
    private fun requestNextNarration() {
        val latest = latestAvailableStopId
        if (latest != null && latest != _navigationState.value.currentLatestStopId) {
            Log.i(TAG, "Narration $latest already queued, not requesting another")
            return
        }
        val requestInFlight = requestedNarrationAfterStopId == latest &&
                SystemClock.elapsedRealtime() - narrationRequestedAtMs < NARRATION_REQUEST_TIMEOUT_MS
        if (narrationRequestedAtMs != 0L && requestInFlight) {
            Log.i(TAG, "Narration after $latest already requested, not requesting another")
            return
        }

        requestedNarrationAfterStopId = latest
        narrationRequestedAtMs = SystemClock.elapsedRealtime()
        navigationScope?.launch {
            routeService.sendLastKnownLocation()
        }
    }

    @MainThread
    fun skipToPrevious() {
        val totalStops = _navigationState.value.totalStops ?: return
        val maxOffset = (totalStops - 1).coerceAtLeast(0)
        _navigationState.update {
            it.copy(historyOffset = (it.historyOffset + 1).coerceAtMost(maxOffset))
        }
    }

    private suspend fun trackCurrentLatestStop() {
        combine(
            latestStopId,
            playbackStateFlow.map { it.isEnded }.distinctUntilChanged(),
            navigationStateFlow.map { it.pendingNextChunkRequestAfterStopId }.distinctUntilChanged()
        ) { latestStopId, isPlaybackEnded, requestedAfterStopId ->
            Triple(latestStopId, isPlaybackEnded, requestedAfterStopId)
        }.collect { (latestStopId, isPlaybackEnded, requestedAfterStopId) ->
            latestAvailableStopId = latestStopId
            initializeCurrentLatestStop(latestStopId)
            advanceStopWhenPlaybackEnds(latestStopId, isPlaybackEnded)
            advanceStopWhenRequestedChunkArrives(latestStopId, requestedAfterStopId)
        }
    }

    private fun initializeCurrentLatestStop(latestStopId: Int?) {
        if (_navigationState.value.currentLatestStopId == null) {
            _navigationState.update { it.copy(currentLatestStopId = latestStopId) }
        }
    }

    private fun advanceStopWhenPlaybackEnds(latestStopId: Int?, isPlaybackEnded: Boolean) {
        val state = _navigationState.value
        val endedItemIsCurrentStop =
            player?.currentMediaItem?.mediaId == state.currentStopId?.toString()
        if (!isPlaybackEnded || !endedItemIsCurrentStop) {
            return
        }

        if (state.historyOffset > 0) {
            _navigationState.update { it.copy(historyOffset = state.historyOffset - 1) }
            return
        }

        val current = state.currentLatestStopId
        if (current == null || (latestStopId != null && current != latestStopId)) {
            Log.i(TAG, "Changing current stop to $latestStopId")
            _navigationState.update { it.copy(currentLatestStopId = latestStopId) }
        }
    }

    private fun advanceStopWhenRequestedChunkArrives(latestStopId: Int?, requestedAfterStopId: Int?) {
        if (latestStopId == null || requestedAfterStopId == null || latestStopId == requestedAfterStopId) {
            return
        }

        _navigationState.update {
            it.copy(
                historyOffset = 0,
                currentLatestStopId = latestStopId,
                pendingNextChunkRequestAfterStopId = null
            )
        }
    }

    private suspend fun syncCurrentStopWithSelectedStop() {
        selectedStopId.collect { stopId ->
            if (stopId != null) {
                _navigationState.update { it.copy(currentStopId = stopId) }
            } else {
                _navigationState.update {
                    it.copy(historyOffset = 0, currentStopId = it.currentLatestStopId)
                }
            }
        }
    }

    private suspend fun trackTotalStops() {
        currentLatestStopId.flatMapLatest { stopId ->
            appDatabase.routeStopDao().getStopsCountUntilStopId(stopId)
        }.collect { total ->
            _navigationState.update { it.copy(totalStops = total) }
        }
    }

    private suspend fun playCurrentStopAudio() {
        currentStop.collect { stop ->
            if (stop == null) {
                return@collect
            }
            val filePath = stop.narrationAudioFilePath
            if (filePath == null) {
                showLoadingPlaceholder(stop)
                return@collect
            }
            if (stop.id != lastPlayedStopId) {
                lastPlayedStopId = stop.id
                playAudioFile(
                    filePath,
                    title = stop.locationTitle,
                    artworkUrl = stop.locationImage,
                    mediaId = stop.id.toString()
                )
            }
        }
    }

    private suspend fun listenForNarrationEvents() {
        eventBus.eventsFlow.collect { event ->
            if (event is AppEventBusEvent.AudioChunkNearlyFinished) {
                val offset = _navigationState.value.historyOffset
                Log.i(
                    TAG,
                    "current offset is $offset, ${if (offset == 0) "requesting" else "skipping"} next narration"
                )
                if (offset == 0) {
                    requestNextNarration()
                }
            }
        }
    }

    private suspend fun showLoadingPlaceholder(stop: RouteStop) {
        withContext(Dispatchers.Main.immediate) {
            ensurePlayer()
            val currentPlayer = player ?: return@withContext
            lastPlayedStopId = null

            val metadata = MediaMetadata.Builder()
                .setTitle(getString(context, R.string.audio_player_loading_next_stop))
                .setArtist(getString(context, R.string.audio_player_loading_narration))
                .apply { stop.locationImage?.let { setArtworkUri(it.toUri()) } }
                .build()

            val placeholder = MediaItem.Builder()
                .setMediaId(NavigatingPlayer.LOADING_MEDIA_ID_PREFIX + stop.id)
                .setUri(Uri.EMPTY)
                .setMediaMetadata(metadata)
                .build()

            currentPlayer.stop()
            currentPlayer.setMediaItem(placeholder)
            publishPlaybackState()
        }
    }

    @MainThread
    fun detachPlayer() {
        navigationScope?.cancel()
        navigationScope = null
        _navigationState.value = RouteNavigationState()
        lastPlayedStopId = null
        latestAvailableStopId = null
        requestedNarrationAfterStopId = null
        narrationRequestedAtMs = 0L
        hasBroadcastLocationNearCurrentNarrationEnd = false
        progressJob?.cancel()
        progressJob = null
        player?.removeListener(playerListener)
        player?.stop()
        player?.clearMediaItems()
        player = null
        autoPlayEnabled = true
        _isPlaying.value = false
        _playbackState.value = RoutePlaybackState()
    }

    suspend fun onDestroy() {
        withContext(Dispatchers.Main.immediate) {
            detachPlayer()
        }
        routeAudioRepository.clearSession()
    }

    val playerListener = object : Player.Listener {
        override fun onIsPlayingChanged(isPlaying: Boolean) {
            _isPlaying.value = isPlaying
            publishPlaybackState()
        }

        override fun onPlaybackStateChanged(playbackState: Int) {
            publishPlaybackState()
        }

        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            publishPlaybackState()
        }
    }

    private companion object {
        private const val TAG = "RouteNarrationPlayback"
        private const val NARRATION_END_LOCATION_BROADCAST_THRESHOLD_MS = 5_000L
        private const val SHORT_NARRATION_END_BROADCAST_FRACTION = 0.8
        private const val NARRATION_REQUEST_TIMEOUT_MS = 30_000L
    }
}
