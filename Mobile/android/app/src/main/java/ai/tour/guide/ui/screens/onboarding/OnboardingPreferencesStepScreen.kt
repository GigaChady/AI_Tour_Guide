package ai.tour.guide.ui.screens.onboarding

import ai.tour.guide.R
import ai.tour.guide.ui.components.onboarding.OnboardingWelcomeText
import ai.tour.guide.ui.navigation.Route
import ai.tour.guide.ui.sharedFragments.preferences.UserPreferenceFragment
import ai.tour.guide.ui.sharedFragments.preferences.UserPreferenceFragmentViewModel
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import org.koin.compose.viewmodel.koinViewModel

@Preview(showBackground = true)
@Composable
fun OnboardingPreferencesStepScreen(
    modifier: Modifier = Modifier,
    viewModel: UserPreferenceFragmentViewModel = koinViewModel(),
    backStack: NavBackStack<NavKey>? = null,
) {
    val viewModelState by viewModel.viewStateFlow.collectAsStateWithLifecycle()

    LifecycleStartEffect(viewModelState.isSuccess) {
        if (viewModelState.isSuccess) {
            backStack?.clear()
            backStack?.add(Route.OnboardingFinishStepScreen)
        }
        onStopOrDispose { }
    }

    Surface(
        modifier = modifier
            .fillMaxSize()
            .testTag("onboarding_preferences_screen"),
        color = MaterialTheme.colorScheme.background
    ) {
        Column() {
            OnboardingWelcomeText(stringResource(R.string.onboarding_step4_header_text_body))
            UserPreferenceFragment(
                modifier = Modifier
                    .weight(1f)
                    .padding(horizontal = 16.dp),
                viewModel = viewModel
            )
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically)
            ) {
                Text(
                    text = stringResource(R.string.onboarding_step4_page_hint),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
                ExtendedFloatingActionButton(
                    modifier = Modifier.testTag("preferences_next"),
                    onClick = {
                        viewModel.onSavePreferencesClicked()
                    },
                    shape = MaterialTheme.shapes.small,
                    icon = { Icon(Icons.AutoMirrored.Default.ArrowForward, null) },
                    text = {
                        Text(
                            text = stringResource(R.string.onboarding_step4_next_button),
                            style = MaterialTheme.typography.titleMediumEmphasized
                        )
                    }
                )
            }
        }
    }
}
