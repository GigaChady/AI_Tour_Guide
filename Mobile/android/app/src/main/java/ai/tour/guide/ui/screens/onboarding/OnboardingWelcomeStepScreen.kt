package ai.tour.guide.ui.screens.onboarding

import ai.tour.guide.R
import ai.tour.guide.ui.navigation.Route
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey

@Preview(showBackground = true)
@Composable
fun OnboardingWelcomeStepScreen(
    modifier: Modifier = Modifier,
    backStack: NavBackStack<NavKey>? = null
) {
    OnboardingAnimatedSharedStepScreen(
        modifier = modifier,
        onNextClicked = {
            backStack?.clear()
            backStack?.add(Route.OnboardingLoginStepScreen)
        },
        headerTitle = stringResource(R.string.onboarding_header_text_header),
        headerBody = stringResource(R.string.onboarding_step1_header_text_body),
        buttonLabel = stringResource(R.string.onboarding_step1_get_started_btn_content),
        screenTestTag = "onboarding_welcome_screen",
        buttonTestTag = "onboarding_welcome_next"
    )
}
