package ai.tour.guide.ui.screens.main.dashboard

import ai.tour.guide.R
import ai.tour.guide.ui.components.display.ImageCarousel
import ai.tour.guide.ui.components.permissions.LocationPermissionGate
import ai.tour.guide.ui.navigation.Route
import ai.tour.guide.ui.theme.AiTourGuideTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import org.koin.compose.koinInject

@Composable
fun DashboardScreen(
    modifier: Modifier = Modifier,
    backStack: NavBackStack<NavKey>? = null,
    viewModel: DashboardViewModel = koinInject()
) {
    val viewModelState by viewModel.latestPoiFlow.collectAsStateWithLifecycle(DashboardState.default())

    LocationPermissionGate(modifier = modifier) {
        val part1 = stringResource(R.string.dashboard_header_text_content_part1)
        val part2 = stringResource(R.string.dashboard_header_text_content_part2)
        val headerText = remember(part1, part2) {
            buildAnnotatedString {
                append(part1)
                append("\n")
                withStyle(style = SpanStyle(fontWeight = FontWeight.Bold)) {
                    append(part2)
                }
            }
        }

        Surface(
            modifier = Modifier
                .fillMaxSize()
                .testTag("dashboard_screen"),
            color = MaterialTheme.colorScheme.background
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Column(
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Text(
                        text = headerText,
                        style = MaterialTheme.typography.displaySmall,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = stringResource(R.string.dashboard_main_section_header),
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.secondary,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Text(
                            text = viewModelState.poiName.ifBlank {
                                stringResource(R.string.dashboard_main_section_header_subtext_example)
                            },
                            style = MaterialTheme.typography.headlineLarge,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }

                ImageCarousel(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    imageUrls = viewModelState.poiPhotos
                )

                ExtendedFloatingActionButton(
                    onClick = {
                        backStack?.clear()
                        backStack?.add(Route.TourAudioPlayer)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("dashboard_start_tour"),
                    icon = {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                            contentDescription = null
                        )
                    },
                    text = {
                        Text(
                            text = stringResource(R.string.dashboard_main_cta_button_text),
                            style = MaterialTheme.typography.titleMediumEmphasized
                        )
                    }
                )
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun DashboardScreenPreview() {
    AiTourGuideTheme {
        DashboardScreen()
    }
}
