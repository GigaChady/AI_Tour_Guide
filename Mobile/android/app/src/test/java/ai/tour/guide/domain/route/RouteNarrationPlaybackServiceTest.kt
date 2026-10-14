package ai.tour.guide.domain.route

import ai.tour.guide.data.room.AppDatabase
import ai.tour.guide.data.room.dao.RouteStopDao
import ai.tour.guide.data.room.entity.RouteStop
import ai.tour.guide.domain.AppEventBus
import ai.tour.guide.domain.AppEventBusEvent
import ai.tour.guide.domain.playback.NarrationPlayerHolder
import android.app.Application
import androidx.media3.common.Player
import androidx.test.core.app.ApplicationProvider
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.shadows.ShadowSystemClock
import java.time.Duration
import org.robolectric.annotation.Config

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = Application::class)
class RouteNarrationPlaybackServiceTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var routeAudioRepository: RouteAudioRepository
    private lateinit var eventBus: AppEventBus
    private lateinit var routeService: RouteService
    private lateinit var routeStopDao: RouteStopDao
    private lateinit var playerHolder: NarrationPlayerHolder
    private lateinit var service: RouteNarrationPlaybackService
    private val events = MutableSharedFlow<AppEventBusEvent>()
    private val latestStopId = MutableStateFlow<Int?>(5)

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        val context = ApplicationProvider.getApplicationContext<Application>()
        routeAudioRepository = mockk(relaxed = true)
        eventBus = mockk(relaxed = true)
        routeService = mockk(relaxed = true)
        routeStopDao = mockk(relaxed = true)
        val appDatabase = mockk<AppDatabase>(relaxed = true)
        playerHolder = NarrationPlayerHolder(context)

        every { eventBus.eventsFlow } returns events
        every { routeService.currentSessionIdFlow } returns MutableStateFlow("session")
        every { appDatabase.routeStopDao() } returns routeStopDao
        every { routeStopDao.getLatestStopIdForServerSession(any()) } returns latestStopId
        every { routeStopDao.getStopsCountUntilStopId(any()) } returns flowOf(2)
        every { routeStopDao.getStopIdByOffsetFromStop(5, 0) } returns flowOf(5)
        every { routeStopDao.getStopIdByOffsetFromStop(5, 1) } returns flowOf(4)
        every { routeStopDao.getStopById(any()) } returns flowOf(null)
        every { routeStopDao.getStopById(5) } returns flowOf(
            RouteStop(id = 5, sessionId = 1, narrationAudioFilePath = "/tmp/stop5.mp3")
        )
        every { routeStopDao.getStopById(4) } returns flowOf(RouteStop(id = 4, sessionId = 1))

        service = RouteNarrationPlaybackService(
            context, routeAudioRepository, eventBus, playerHolder, routeService, appDatabase
        )
    }

    private fun runNavigationTest(block: suspend TestScope.() -> Unit) = runTest {
        try {
            block()
        } finally {
            service.detachPlayer()
        }
    }

    @After
    fun tearDown() {
        service.detachPlayer()
        playerHolder.release()
        Dispatchers.resetMain()
    }

    @Test
    fun `isPlayingFlow starts as false`() {
        assertFalse(service.isPlayingFlow.value)
    }

    @Test
    fun `playbackStateFlow starts as default RoutePlaybackState`() {
        assertEquals(RoutePlaybackState(), service.playbackStateFlow.value)
    }

    @Test
    fun `pauseNarration sets isPlaying to false`() = runTest {
        service.pauseNarration()
        advanceUntilIdle()

        assertFalse(service.isPlayingFlow.value)
    }

    @Test
    fun `pauseNarration works before player is initialized`() = runTest {
        // No playAudioFile called — player is null; pauseNarration must not crash
        service.pauseNarration()
        advanceUntilIdle()

        assertFalse(service.isPlayingFlow.value)
    }

    @Test
    fun `onDestroy sets isPlaying to false`() = runTest {
        service.onDestroy()
        advanceUntilIdle()

        assertFalse(service.isPlayingFlow.value)
    }

    @Test
    fun `onDestroy resets playbackState to default`() = runTest {
        service.onDestroy()
        advanceUntilIdle()

        assertEquals(RoutePlaybackState(), service.playbackStateFlow.value)
    }

    @Test
    fun `onDestroy calls routeAudioRepository clearSession`() = runTest {
        service.onDestroy()
        advanceUntilIdle()

        coVerify(exactly = 1) { routeAudioRepository.clearSession() }
    }

    @Test
    fun `startNavigation selects latest stop`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        val state = service.navigationStateFlow.value
        assertEquals(5, state.currentLatestStopId)
        assertEquals(5, state.currentStopId)
        assertEquals(2, state.totalStops)
    }

    @Test
    fun `skipToNext at offset zero requests next chunk`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        service.skipToNext()
        runCurrent()

        assertEquals(5, service.navigationStateFlow.value.pendingNextChunkRequestAfterStopId)
        coVerify(exactly = 1) { routeService.sendLastKnownLocation() }
    }

    @Test
    fun `skipToNext in history moves towards latest stop`() = runNavigationTest {
        service.startNavigation()
        runCurrent()
        service.skipToPrevious()
        runCurrent()

        service.skipToNext()
        runCurrent()

        val state = service.navigationStateFlow.value
        assertEquals(0, state.historyOffset)
        assertEquals(5, state.currentStopId)
        coVerify(exactly = 0) { routeService.sendLastKnownLocation() }
    }

    @Test
    fun `skipToPrevious clamps to first stop`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        service.skipToPrevious()
        service.skipToPrevious()
        runCurrent()

        val state = service.navigationStateFlow.value
        assertEquals(1, state.historyOffset)
        assertEquals(4, state.currentStopId)
    }

    @Test
    fun `skipToPrevious does nothing when totalStops is unknown`() {
        service.skipToPrevious()

        assertEquals(0, service.navigationStateFlow.value.historyOffset)
    }

    @Test
    fun `AudioChunkNearlyFinished sends location only at offset zero`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        events.emit(AppEventBusEvent.AudioChunkNearlyFinished(0L))
        runCurrent()
        coVerify(exactly = 1) { routeService.sendLastKnownLocation() }

        service.skipToPrevious()
        runCurrent()
        events.emit(AppEventBusEvent.AudioChunkNearlyFinished(0L))
        runCurrent()
        coVerify(exactly = 1) { routeService.sendLastKnownLocation() }
    }

    @Test
    fun `player only holds the current stop`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        val player = playerHolder.get()
        assertEquals(1, player.mediaItemCount)
        assertEquals("5", player.currentMediaItem?.mediaId)

        service.skipToPrevious()
        runCurrent()
        assertEquals(1, player.mediaItemCount)
        assertEquals("loading:4", player.currentMediaItem?.mediaId)
        assertEquals(Player.STATE_IDLE, player.playbackState)
    }

    @Test
    fun `skipToNext does not request again while a request is in flight`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        service.skipToNext()
        service.skipToNext()
        runCurrent()

        coVerify(exactly = 1) { routeService.sendLastKnownLocation() }
    }

    @Test
    fun `skipToNext after nearly finished request does not request again`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        events.emit(AppEventBusEvent.AudioChunkNearlyFinished(0L))
        runCurrent()
        service.skipToNext()
        runCurrent()

        coVerify(exactly = 1) { routeService.sendLastKnownLocation() }
    }

    @Test
    fun `skipToNext plays already queued narration without requesting`() = runNavigationTest {
        service.startNavigation()
        runCurrent()
        latestStopId.value = 6
        runCurrent()

        service.skipToNext()
        runCurrent()

        assertEquals(6, service.navigationStateFlow.value.currentLatestStopId)
        coVerify(exactly = 0) { routeService.sendLastKnownLocation() }
    }

    @Test
    fun `nearly finished does not request when narration is already queued`() = runNavigationTest {
        service.startNavigation()
        runCurrent()
        latestStopId.value = 6
        runCurrent()

        events.emit(AppEventBusEvent.AudioChunkNearlyFinished(0L))
        runCurrent()

        coVerify(exactly = 0) { routeService.sendLastKnownLocation() }
    }

    @Test
    fun `request can be retried after it times out`() = runNavigationTest {
        service.startNavigation()
        runCurrent()

        service.skipToNext()
        runCurrent()
        ShadowSystemClock.advanceBy(Duration.ofSeconds(31))
        service.skipToNext()
        runCurrent()

        coVerify(exactly = 2) { routeService.sendLastKnownLocation() }
    }
}
