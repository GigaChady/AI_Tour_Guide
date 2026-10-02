package ai.tour.guide.ui.screens.onboarding.auth

import ai.tour.guide.R
import ai.tour.guide.ui.components.onboarding.OnboardingWelcomeText
import ai.tour.guide.ui.navigation.Route
import ai.tour.guide.ui.sharedFragments.UserRegistrationFragment
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey

@Preview(showBackground = true)
@Composable
fun OnboardingRegisterStepScreen(
    modifier: Modifier = Modifier,
    backStack: NavBackStack<NavKey>? = null,
) {
    Surface(
        modifier = modifier
            .fillMaxSize()
            .testTag("onboarding_register_screen"),
        color = MaterialTheme.colorScheme.background
    ) {
        Column() {
            OnboardingWelcomeText(stringResource(R.string.onboarding_step3_header_text_body))
            UserRegistrationFragment(
                onChangesSaved = {
                    backStack?.clear()
                    backStack?.add(Route.OnboardingPreferencesStepScreen)
                },
                ctaButtonText = stringResource(R.string.onboarding_step3_register_button)
            )
        }
    }
}
