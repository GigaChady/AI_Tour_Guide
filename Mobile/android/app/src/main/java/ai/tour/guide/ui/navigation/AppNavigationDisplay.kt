package ai.tour.guide.ui.navigation

import ai.tour.guide.R
import ai.tour.guide.ui.navigation.wrappers.WithDrawerLayout
import ai.tour.guide.ui.navigation.wrappers.WithOnlySafeDrawingPadding
import ai.tour.guide.ui.navigation.wrappers.WithScreenTopBar
import ai.tour.guide.ui.screens.main.AccountSettingsScreen
import ai.tour.guide.ui.screens.main.appSettings.AppSettingsScreen
import ai.tour.guide.ui.screens.main.map.MapScreen
import ai.tour.guide.ui.screens.main.ProfilePreferencesScreen
import ai.tour.guide.ui.screens.main.route.TourRouteSummaryScreen
import ai.tour.guide.ui.screens.main.dashboard.DashboardScreen
import ai.tour.guide.ui.screens.main.route.TourAudioPlayerScreen
import ai.tour.guide.ui.screens.onboarding.OnboardingPreferencesStepScreen
import ai.tour.guide.ui.screens.onboarding.OnboardingWelcomeStepScreen
import ai.tour.guide.ui.screens.onboarding.auth.OnboardingLoginStepScreen
import ai.tour.guide.ui.screens.onboarding.auth.OnboardingRegisterStepScreen
import ai.tour.guide.ui.screens.onboarding.finish.OnboardingFinishStepScreen
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import androidx.navigation3.runtime.entryProvider
import androidx.navigation3.runtime.rememberNavBackStack
import androidx.navigation3.ui.NavDisplay
import kotlinx.coroutines.launch

@Composable
fun AppNavigationDisplay(modifier: Modifier = Modifier, initialRoute: Route = Route.Dashboard) {
    val backStack = rememberNavBackStack(initialRoute)

    NavDisplay(
        modifier = modifier.fillMaxSize(),
        backStack = backStack,
        onBack = { backStack.removeLastOrNull() },
        entryProvider = entryProvider {
            // Dashboard
            entry<Route.Dashboard>(
                metadata = NavDisplay.transitionSpec { EnterTransition.None togetherWith ExitTransition.None }
            ) {
                WithDrawerLayout(
                    backStack = backStack,
                    routeTitle = stringResource(R.string.navigation_dashboard_route_title)
                ) {
                    DashboardScreen(
                        backStack = backStack
                    )
                }
            }
            entry<Route.Profile>(
                metadata = NavDisplay.transitionSpec { EnterTransition.None togetherWith ExitTransition.None }
            ) {
                WithDrawerLayout(
                    backStack = backStack,
                    routeTitle = stringResource(R.string.navigation_profile_preferences_route_title)
                ) {
                    ProfilePreferencesScreen()
                }
            }
            entry<Route.Settings>(
                metadata = NavDisplay.transitionSpec { EnterTransition.None togetherWith ExitTransition.None }
            ) {
                WithDrawerLayout(
                    backStack = backStack,
                    routeTitle = stringResource(R.string.navigation_app_settings_route_title)
                ) { AppSettingsScreen(backStack = backStack) }
            }
            entry<Route.AccountSettings> {
                WithScreenTopBar(
                    backStack = backStack,
                    hasBackButton = true,
                    routeTitle = stringResource(R.string.navigation_account_settings_route_title)
                ) { AccountSettingsScreen() }
            }

            // Main navigation flow
            entry<Route.TourAudioPlayer> {
                WithScreenTopBar(
                    backStack = backStack,
                    topBarActions = { TourAudioPlayerMapIcon(backStack = backStack) },
                    routeTitle = stringResource(R.string.navigation_tour_audio_player_route_title)
                ) {
                    TourAudioPlayerScreen(
                        backStack = backStack
                    )
                }
            }
            entry<Route.MapUserPosition> {
                WithScreenTopBar(
                    backStack = backStack,
                    hasBackButton = true,
                    routeTitle = stringResource(R.string.navigation_map_user_position_route_title)
                ) {
                    MapScreen(
                        backStack = backStack
                    )
                }
            }

            entry<Route.TripEndSummary> {
                WithScreenTopBar(backStack = backStack) {
                    TourRouteSummaryScreen(
                        backStack = backStack
                    )
                }
            }

            // Onboarding
            entry<Route.OnboardingFinishStepScreen> {
                OnboardingFinishStepScreen(
                    backStack = backStack
                )
            }
            entry<Route.OnboardingRegisterStepScreen> {
                WithOnlySafeDrawingPadding {
                    OnboardingRegisterStepScreen(
                        backStack = backStack
                    )
                }
            }
            entry<Route.OnboardingLoginStepScreen> {
                WithOnlySafeDrawingPadding {
                    OnboardingLoginStepScreen(
                        backStack = backStack
                    )
                }
            }
            entry<Route.OnboardingPreferencesStepScreen> {
                WithOnlySafeDrawingPadding {
                    OnboardingPreferencesStepScreen(
                        backStack = backStack
                    )
                }
            }
            entry<Route.OnboardingWelcomeStepScreen> {
                OnboardingWelcomeStepScreen(
                    backStack = backStack
                )
            }
        },
        transitionSpec = {
            slideInHorizontally(
                initialOffsetX = { it },
                animationSpec = tween(300)
            ) togetherWith slideOutHorizontally(
                targetOffsetX = { -it },
                animationSpec = tween(300)
            )
        },
        popTransitionSpec = {
            slideInHorizontally(
                initialOffsetX = { -it },
                animationSpec = tween(300)
            ) togetherWith slideOutHorizontally(
                targetOffsetX = { it },
                animationSpec = tween(300)
            )
        },
        predictivePopTransitionSpec = {
            slideInHorizontally(
                initialOffsetX = { -it },
                animationSpec = tween(300)
            ) togetherWith slideOutHorizontally(
                targetOffsetX = { it },
                animationSpec = tween(300)
            )
        }
    )
}

@Composable
fun TourAudioPlayerMapIcon(modifier: Modifier = Modifier, backStack: NavBackStack<NavKey>) {
    val scope = rememberCoroutineScope()
    IconButton(
        modifier = modifier.testTag("tour_open_map"),
        onClick = {
            scope.launch { backStack.add(Route.MapUserPosition) }
        }
    ) {
        Icon(
            imageVector = Icons.Default.LocationOn,
            contentDescription = stringResource(R.string.app_bar_map_icon_tour_content_description)
        )
    }
}
