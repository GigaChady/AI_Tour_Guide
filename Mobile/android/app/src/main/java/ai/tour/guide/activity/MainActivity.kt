package ai.tour.guide.activity

import ai.tour.guide.data.appData.AppDataRepository
import ai.tour.guide.data.appSettings.AppSettingsAppThemeType
import ai.tour.guide.ui.navigation.AppNavigationDisplay
import ai.tour.guide.ui.navigation.Route
import ai.tour.guide.ui.theme.AiTourGuideTheme
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import org.koin.android.ext.android.inject

class MainActivity : ComponentActivity() {
    val appDataRepository: AppDataRepository by inject()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val onboardingCompleted by appDataRepository.onboardingCompletedFlow.collectAsState(
                initial = null
            )

            val currentAppTheme by appDataRepository.appThemeFlow.collectAsState(
                initial = AppSettingsAppThemeType.SYSTEM
            )

            val isSystemDark = isSystemInDarkTheme()
            val isDarkTheme = when (currentAppTheme) {
                AppSettingsAppThemeType.LIGHT -> false
                AppSettingsAppThemeType.DARK -> true
                AppSettingsAppThemeType.SYSTEM -> isSystemDark
            }

            AiTourGuideTheme(darkTheme = isDarkTheme) {
                onboardingCompleted?.let { completed ->
                    val startRoute = if (!completed) {
                        Route.OnboardingWelcomeStepScreen
                    } else {
                        Route.Dashboard
                    }
                    key(completed) {
                        AppNavigationDisplay(
                            modifier = Modifier.semantics {
                                testTagsAsResourceId = true
                            },
                            initialRoute = startRoute
                        )
                    }
                }
            }
        }
    }
}
