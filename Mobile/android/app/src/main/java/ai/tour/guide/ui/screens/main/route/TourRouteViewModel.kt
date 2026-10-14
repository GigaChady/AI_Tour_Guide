package ai.tour.guide.ui.screens.main.route

import ai.tour.guide.data.room.AppDatabase
import ai.tour.guide.data.shared.BaseViewModel
import ai.tour.guide.domain.AppEventBus
import ai.tour.guide.domain.AppEventBusEvent
import ai.tour.guide.domain.route.RouteNarrationPlaybackService
import ai.tour.guide.domain.route.RouteService
import ai.tour.guide.domain.route.RouteSessionBackgroundService
import ai.tour.guide.network.schema.response.NarrationWordDto
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import org.koin.core.annotation.KoinViewModel

@KoinViewModel
class TourRouteViewModel(
    private val appContext: Context,
    val routeAudioService: RouteNarrationPlaybackService,
    val routeService: RouteService,
    val appEventBus: AppEventBus,
    val appDatabase: AppDatabase
) :
    BaseViewModel<TourRouteState>(TourRouteState.default()) {
    val isPlayingFlow: StateFlow<Boolean> = routeAudioService.isPlayingFlow
    val playbackStateFlow = routeAudioService.playbackStateFlow
    private val sessionId: StateFlow<String?> = routeService.currentSessionIdFlow
    private var stopStateListenersJob: Job? = null
    private var eventListenersJob: Job? = null

    private val navigationState = routeAudioService.navigationStateFlow
    private val currentStopId = navigationState.map { it.currentStopId }.distinctUntilChanged()
    private val currentLatestStopId =
        navigationState.map { it.currentLatestStopId }.distinctUntilChanged()

    private var hasStarted = false

    @OptIn(ExperimentalCoroutinesApi::class)
    val stopsCount = currentLatestStopId.flatMapLatest { stopId ->
        appDatabase.routeStopDao().getStopsCountUntilStopId(stopId)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    val currentStopIndex = currentStopId.flatMapLatest { stopId ->
        appDatabase.routeStopDao().getStopIndexById(stopId)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    val currentStopFlow = currentStopId.flatMapLatest { stopId ->
        Log.i(TAG, "Getting stop $stopId")
        appDatabase.routeStopDao().getStopById(stopId)
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    val playerEnabledFlow = sessionId.flatMapLatest { id ->
        appDatabase.routeStopDao().narrationFilesExistsForCurrentSession(id)
    }

    private fun startStopStateListeners() {
        if (stopStateListenersJob?.isActive == true) {
            return
        }

        stopStateListenersJob = viewModelScope.launch {
            launch { mirrorCurrentStopId() }
            launch { updateRoutePresentationState() }
        }
    }

    private suspend fun mirrorCurrentStopId() {
        currentStopId.collect { stopId ->
            updateData { copy(currentStopId = stopId) }
        }
    }

    private suspend fun updateRoutePresentationState() {
        combine(
            currentStopFlow,
            playbackStateFlow,
            currentStopIndex,
            stopsCount
        ) { stop, playback, index, total ->
            Triple(stop, playback, Pair(index, total))
        }.collect { (stop, playback, counts) ->
            val (index, total) = counts
            val text = stop?.narrationString ?: ""
            val words = stop?.narrationWordsMap ?: emptyList()

            val narrationText = buildNarrationText(
                text = text,
                words = words,
                playbackPositionMs = playback.positionMs,
                playbackDurationMs = playback.durationMs
            )
            updateData {
                copy(
                    text = text,
                    styledText = narrationText.text,
                    currentWordStartOffset = narrationText.currentWordStartOffset,
                    words = words,
                    currentStopIndex = index,
                    totalStops = total
                )
            }
        }
    }

    private suspend fun initEventListeners() {
        appEventBus.eventsFlow.collect { event ->
            when (event) {
                is AppEventBusEvent.RouteTimeout -> {
                    Log.i(TAG, "Route timeout: ${event.reason}")
                    updateData {
                        copy(
                            isSuccess = true,
                        )
                    }
                }

                else -> {}
            }
        }
    }

    private fun onTourStart() {
        try {
            ContextCompat.startForegroundService(
                appContext, Intent(appContext, RouteSessionBackgroundService::class.java)
            )
        } catch (e: SecurityException) {
            Log.e(TAG, "Missing location permission, cant start $TAG", e)
        }

    }

    fun onDestroy() {
        appContext.stopService(Intent(appContext, RouteSessionBackgroundService::class.java))
        stopStateListenersJob?.cancel()
        stopStateListenersJob = null
        eventListenersJob?.cancel()
        eventListenersJob = null
        hasStarted = false
        updateData { TourRouteState.default() }
    }

    fun onPlayClicked() {
        viewModelScope.launch {
            routeAudioService.playNarration()
        }
    }

    fun onPauseClicked() {
        viewModelScope.launch {
            routeAudioService.pauseNarration()
        }
    }

    fun onStart() {
        if (hasStarted) return
        hasStarted = true

        startStopStateListeners()
        if (eventListenersJob?.isActive != true) {
            eventListenersJob = viewModelScope.launch {
                initEventListeners()
            }
        }
        viewModelScope.launch {
            onTourStart()
        }
    }

    private fun buildNarrationText(
        text: String,
        words: List<NarrationWordDto>,
        playbackPositionMs: Long,
        playbackDurationMs: Long
    ): NarrationTextPresentation {
        var currentWordStartOffset: Int? = null
        var searchStartIndex = 0
        val styledText = buildAnnotatedString {
            append(text)

            words.forEach { word ->
                if (word.text.isEmpty()) {
                    return@forEach
                }

                val wordStartOffset = text.indexOf(
                    string = word.text,
                    startIndex = searchStartIndex,
                    ignoreCase = false
                )
                if (wordStartOffset == -1) {
                    return@forEach
                }

                val wordEndOffset = wordStartOffset + word.text.length
                if (shouldHighlightWord(word, playbackPositionMs, playbackDurationMs)) {
                    currentWordStartOffset = wordStartOffset
                    addStyle(
                        style = SpanStyle(fontWeight = FontWeight.Bold),
                        start = wordStartOffset,
                        end = wordEndOffset
                    )
                }

                searchStartIndex = wordEndOffset
            }
        }

        return NarrationTextPresentation(
            text = styledText,
            currentWordStartOffset = currentWordStartOffset
        )
    }

    private fun shouldHighlightWord(
        word: NarrationWordDto,
        playbackPositionMs: Long,
        playbackDurationMs: Long
    ): Boolean {
        if (playbackDurationMs <= 0L) {
            return false
        }

        return playbackPositionMs.coerceAtMost(playbackDurationMs).toDouble() >= word.offsetMs
    }

    fun onNextClicked() {
        routeAudioService.skipToNext()
    }

    fun onPrevClicked() {
        routeAudioService.skipToPrevious()
    }

    fun endTour() {
        onDestroy()
    }

    override fun onCleared() {
        super.onCleared()
        onDestroy()
    }

    private companion object {
        const val TAG = "TourRouteViewModel"
    }
}

data class NarrationTextPresentation(
    val text: AnnotatedString,
    val currentWordStartOffset: Int?
)
