package ai.tour.guide.ui.screens.main.route

import ai.tour.guide.R
import ai.tour.guide.ui.components.audio.AudioPlayerWidget
import ai.tour.guide.ui.navigation.Route
import ai.tour.guide.ui.sharedFragments.tourSummary.TourSummaryBottomSheet
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import coil3.compose.AsyncImage
import org.koin.compose.viewmodel.koinViewModel

@Preview(showBackground = true)
@Composable
fun TourAudioPlayerScreen(
    modifier: Modifier = Modifier,
    backStack: NavBackStack<NavKey>? = null,
    viewModel: TourRouteViewModel = koinViewModel()
) {
    val viewModelState by viewModel.viewStateFlow.collectAsStateWithLifecycle()
    val isPlaying by viewModel.isPlayingFlow.collectAsStateWithLifecycle()
    val playbackState by viewModel.playbackStateFlow.collectAsStateWithLifecycle()
    val playerEnabled by viewModel.playerEnabledFlow.collectAsStateWithLifecycle(false)
    val currentStopIdx by viewModel.currentStopIndex.collectAsStateWithLifecycle(1)
    val allStopsCount by viewModel.stopsCount.collectAsStateWithLifecycle(1)
    val currentStop by viewModel.currentStopFlow.collectAsStateWithLifecycle(null)

    var showBottomSheet by remember { mutableStateOf(false) }
    val narrationScrollState = rememberScrollState()
    var narrationTextLayoutResult by remember { mutableStateOf<TextLayoutResult?>(null) }
    val progressFraction = remember(playbackState.positionMs, playbackState.durationMs) {
        if (playbackState.durationMs <= 0L) {
            0f
        } else {
            (playbackState.positionMs.toFloat() / playbackState.durationMs.toFloat()).coerceIn(
                0f,
                1f
            )
        }
    }

    LaunchedEffect(viewModelState.data.currentWordStartOffset, narrationTextLayoutResult) {
        val currentWordStartOffset =
            viewModelState.data.currentWordStartOffset ?: return@LaunchedEffect
        val layoutResult = narrationTextLayoutResult ?: return@LaunchedEffect
        if (currentWordStartOffset !in 0 until layoutResult.layoutInput.text.length) {
            return@LaunchedEffect
        }

        val wordTop = layoutResult
            .getBoundingBox(currentWordStartOffset)
            .top
            .toInt()
        narrationScrollState.animateScrollTo(
            value = (wordTop - NARRATION_SCROLL_TOP_PADDING_PX).coerceIn(
                minimumValue = 0,
                maximumValue = narrationScrollState.maxValue
            )
        )
    }

    val onSessionFinished = {
        backStack?.clear()
        backStack?.add(Route.TripEndSummary)
    }

    LaunchedEffect(viewModelState.data.isSuccess) {
        if (viewModelState.data.isSuccess) {
            onSessionFinished()
        }
    }

    LifecycleStartEffect(Unit) {
        viewModel.onStart()

        onStopOrDispose {
            val isStillInBackStack = backStack?.any { it == Route.TourAudioPlayer } ?: false
            if (!isStillInBackStack) {
                viewModel.onDestroy()
            }
        }
    }

    Surface(
        modifier = modifier
            .fillMaxSize()
            .testTag("tour_screen"),
        color = MaterialTheme.colorScheme.background
    ) {
        TourSummaryBottomSheet(
            showBottomSheet = showBottomSheet,
            onDismissRequest = { showBottomSheet = false },
            activeStopIdOverride = viewModelState.data.currentStopId
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Column {
                Text(
                    text = stringResource(R.string.tour_audio_player_location_header),
                    color = MaterialTheme.colorScheme.onBackground,
                    style = MaterialTheme.typography.labelLarge
                )
                Text(
                    text = currentStop?.locationTitle?.takeIf { it.isNotBlank() }
                        ?: stringResource(R.string.tour_audio_player_example_location),
                    color = MaterialTheme.colorScheme.onBackground,
                    style = MaterialTheme.typography.headlineMedium
                )
            }

            if (!currentStop?.locationImage.isNullOrBlank()) {
                AsyncImage(
                    modifier = Modifier
                        .fillMaxHeight(0.3f)
                        .fillMaxWidth()
                        .padding(0.dp),
                    model = currentStop?.locationImage,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                )
            } else {
                Box(
                    modifier = Modifier
                        .fillMaxHeight(0.3f)
                        .fillMaxWidth()
                        .padding(0.dp),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.fillMaxWidth(0.2f)
                    )
                }
            }

            Text(
                text = stringResource(R.string.tour_audio_player_narration_header_title),
                color = MaterialTheme.colorScheme.onBackground,
                style = MaterialTheme.typography.labelLarge
            )
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .verticalScroll(narrationScrollState)
            ) {
                Text(
                    text = viewModelState.data.styledText,
                    color = MaterialTheme.colorScheme.outline,
                    style = MaterialTheme.typography.bodyLarge,
                    onTextLayout = { narrationTextLayoutResult = it }
                )
            }
            AudioPlayerWidget(
                controlsEnabled = playerEnabled,
                onEndClicked = {
                    viewModel.endTour()
                    onSessionFinished()
                },
                onInfoClicked = {
                    showBottomSheet = true
                },
                onPreviousClicked = {
                    viewModel.onPrevClicked()
                },
                onPlayClicked = {
                    viewModel.onPlayClicked()
                },
                onPauseClicked = {
                    viewModel.onPauseClicked()
                },
                onNextClicked = {
                    viewModel.onNextClicked()
                },
                isPlaying = isPlaying,
                progressFraction = progressFraction,
                totalMediaCount = allStopsCount,
                currentMediaIndex = currentStopIdx
            )
        }
    }
}

private const val NARRATION_SCROLL_TOP_PADDING_PX = 48
