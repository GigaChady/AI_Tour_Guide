package ai.tour.guide.ui.screens.main.route

import ai.tour.guide.data.room.AppDatabase
import ai.tour.guide.data.room.dao.RouteStopDao
import ai.tour.guide.domain.AppEventBus
import ai.tour.guide.domain.route.RouteNarrationPlaybackService
import ai.tour.guide.domain.route.RouteNavigationState
import ai.tour.guide.domain.route.RoutePlaybackState
import ai.tour.guide.domain.route.RouteService
import ai.tour.guide.domain.route.RouteSessionBackgroundService
import android.app.Application
import androidx.test.core.app.ApplicationProvider
import io.mockk.coVerify
import io.mockk.every
import io.mockk.verify
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = Application::class)
class TourRouteViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var routeAudioService: RouteNarrationPlaybackService
    private lateinit var routeService: RouteService
    private lateinit var appEventBus: AppEventBus
    private lateinit var appDatabase: AppDatabase
    private lateinit var routeStopDao: RouteStopDao
    private lateinit var viewModel: TourRouteViewModel
    private lateinit var appContext: Application

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)

        routeAudioService = mockk(relaxed = true)
        routeService = mockk(relaxed = true)
        appEventBus = mockk(relaxed = true)
        appDatabase = mockk(relaxed = true)
        routeStopDao = mockk(relaxed = true)

        every { routeAudioService.isPlayingFlow } returns MutableStateFlow(false)
        every { routeAudioService.playbackStateFlow } returns MutableStateFlow(RoutePlaybackState())
        every { routeAudioService.navigationStateFlow } returns MutableStateFlow(RouteNavigationState())
        every { routeService.currentSessionIdFlow } returns MutableStateFlow(null)
        every { appEventBus.eventsFlow } returns MutableSharedFlow()
        every { appDatabase.routeStopDao() } returns routeStopDao
        every { routeStopDao.getStopsCountUntilStopId(any()) } returns flowOf(null)
        every { routeStopDao.getStopIdByOffsetFromStop(any(), any()) } returns flowOf(null)
        every { routeStopDao.getStopIndexById(any()) } returns flowOf(null)
        every { routeStopDao.getStopById(any()) } returns flowOf(null)
        every { routeStopDao.getLatestStopIdForServerSession(any()) } returns flowOf(null)
        every { routeStopDao.narrationFilesExistsForCurrentSession(any()) } returns flowOf(false)

        appContext = ApplicationProvider.getApplicationContext()
        viewModel = TourRouteViewModel(
            appContext, routeAudioService, routeService, appEventBus, appDatabase
        )
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `isPlayingFlow mirrors routeAudioService isPlayingFlow`() {
        assertTrue(viewModel.isPlayingFlow === routeAudioService.isPlayingFlow)
    }

    @Test
    fun `onPlayClicked calls routeAudioService playNarration`() = runTest {
        viewModel.onPlayClicked()
        advanceUntilIdle()

        coVerify(exactly = 1) { routeAudioService.playNarration() }
    }

    @Test
    fun `onPauseClicked calls routeAudioService pauseNarration`() = runTest {
        viewModel.onPauseClicked()
        advanceUntilIdle()

        coVerify(exactly = 1) { routeAudioService.pauseNarration() }
    }

    @Test
    fun `onDestroy stops RouteSessionBackgroundService`() = runTest {
        viewModel.onDestroy()
        advanceUntilIdle()

        val stopped = shadowOf(appContext).nextStoppedService
        assertNotNull(stopped)
        assertEquals(RouteSessionBackgroundService::class.java.name, stopped.component?.className)
    }

    @Test
    fun `onDestroy resets view state to default`() = runTest {
        viewModel.onDestroy()
        advanceUntilIdle()

        assertEquals(TourRouteState.default(), viewModel.viewStateFlow.value.data)
    }

    @Test
    fun `onStart starts RouteSessionBackgroundService`() = runTest {
        viewModel.onStart()
        advanceUntilIdle()

        val started = shadowOf(appContext).nextStartedService
        assertNotNull(started)
        assertEquals(RouteSessionBackgroundService::class.java.name, started.component?.className)
    }

    @Test
    fun `onNextClicked delegates to routeAudioService skipToNext`() {
        viewModel.onNextClicked()

        verify(exactly = 1) { routeAudioService.skipToNext() }
    }

    @Test
    fun `onPrevClicked delegates to routeAudioService skipToPrevious`() {
        viewModel.onPrevClicked()

        verify(exactly = 1) { routeAudioService.skipToPrevious() }
    }
}
