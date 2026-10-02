package ai.tour.guide.ui.components.audio

import ai.tour.guide.R
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.outlined.Cancel
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Pause
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonColors
import androidx.compose.material3.LinearWavyProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Preview(showBackground = true)
@Composable
fun AudioPlayerWidget(
    onEndClicked: () -> Unit = {},
    onInfoClicked: () -> Unit = {},
    onPreviousClicked: () -> Unit = {},
    onPlayClicked: () -> Unit = {},
    onPauseClicked: () -> Unit = {},
    onNextClicked: () -> Unit = {},
    isPlaying: Boolean = false,
    progressFraction: Float = 0f,
    controlsEnabled: Boolean = true,
    totalMediaCount: Int? = null,
    currentMediaIndex: Int? = null
) {
    val idx = currentMediaIndex ?: 0
    val total = totalMediaCount ?: 1
    Column(
        modifier = Modifier
            .fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Row(
            horizontalArrangement = Arrangement.SpaceBetween,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 4.dp)
        ) {
            Text(
                text = stringResource(R.string.audio_player_widget_header_text),
                color = MaterialTheme.colorScheme.onBackground,
                style = MaterialTheme.typography.labelLarge
            )
            Text(
                text = "$idx/$total",
                color = MaterialTheme.colorScheme.onBackground,
                style = MaterialTheme.typography.labelLarge
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FilledTonalIconButton(
                onClick = onInfoClicked,
                enabled = true,
                shape = CircleShape,
                modifier = Modifier.size(42.dp)
            ) {
                Icon(
                    imageVector = Icons.Outlined.Info,
                    contentDescription = null
                )
            }
            FilledTonalIconButton(
                onClick = onPreviousClicked,
                enabled = controlsEnabled,
                shape = CircleShape,
                modifier = Modifier.size(58.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.SkipPrevious,
                    contentDescription = null
                )
            }
            FilledTonalIconButton(
                onClick = if (isPlaying) onPauseClicked else onPlayClicked,
                enabled = controlsEnabled,
                shape = CircleShape,
                modifier = Modifier.size(72.dp)
            ) {
                Icon(
                    imageVector = if (isPlaying) Icons.Outlined.Pause else Icons.Outlined.PlayArrow,
                    contentDescription = null
                )
            }
            FilledTonalIconButton(
                onClick = onNextClicked,
                enabled = controlsEnabled,
                shape = CircleShape,
                modifier = Modifier.size(58.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.SkipNext,
                    contentDescription = null
                )
            }
            FilledTonalIconButton(
                onClick = onEndClicked,
                enabled = true,
                shape = CircleShape,
                modifier = Modifier
                    .size(42.dp)
                    .testTag("tour_end"),
                colors = IconButtonColors(
                    containerColor = MaterialTheme.colorScheme.error,
                    contentColor = MaterialTheme.colorScheme.onError,
                    disabledContainerColor = MaterialTheme.colorScheme.error,
                    disabledContentColor = MaterialTheme.colorScheme.onError,
                )
            ) {
                Icon(
                    imageVector = Icons.Outlined.Cancel,
                    contentDescription = null
                )
            }
        }
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            LinearWavyProgressIndicator(
                modifier = Modifier.fillMaxWidth(0.95f),
                progress = { progressFraction.coerceIn(0f, 1f) },
                waveSpeed = 16.dp
            )
        }
    }
}
