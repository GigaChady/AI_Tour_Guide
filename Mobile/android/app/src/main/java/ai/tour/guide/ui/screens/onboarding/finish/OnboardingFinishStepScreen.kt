package ai.tour.guide.ui.screens.onboarding.finish

import ai.tour.guide.R
import ai.tour.guide.ui.navigation.Route
import ai.tour.guide.ui.screens.onboarding.OnboardingAnimatedSharedStepScreen
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import org.koin.compose.viewmodel.koinViewModel

@Preview(showBackground = true)
@Composable
fun OnboardingFinishStepScreen(
    modifier: Modifier = Modifier,
    viewModel: OnboardingFinishStepViewModel = koinViewModel(),
    backStack: NavBackStack<NavKey>? = null
) {
    val finished by viewModel.completedStateFlow.collectAsStateWithLifecycle()

    LifecycleStartEffect(finished) {
        if (finished) {
            backStack?.clear()
            backStack?.add(Route.Dashboard)
        }
        onStopOrDispose { }
    }

    OnboardingAnimatedSharedStepScreen(
        onNextClicked = {
            viewModel.onFinishClicked()
        },
        modifier = modifier,
        headerTitle = stringResource(R.string.onboarding_step5_header_text_header),
        headerBody = stringResource(R.string.onboarding_step5_header_text_body),
        buttonLabel = stringResource(R.string.onboarding_step5_get_started_btn_content),
        screenTestTag = "onboarding_finish_screen",
        buttonTestTag = "onboarding_finish_next"
    )
}
