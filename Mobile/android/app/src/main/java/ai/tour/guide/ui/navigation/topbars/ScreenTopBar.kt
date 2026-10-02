package ai.tour.guide.ui.navigation.topbars

import ai.tour.guide.R
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScreenTopBar(
    backStack: NavBackStack<NavKey>,
    hasBackButton: Boolean = false,
    routeTitle: String = "",
    actions: @Composable () -> Unit = {}
) {
    val scope = rememberCoroutineScope()

    CenterAlignedTopAppBar(
        title = {
            Text(
                text = routeTitle
            )
        },
        navigationIcon = {
            if (hasBackButton) {
                IconButton(
                    modifier = Modifier.testTag("top_bar_back"),
                    onClick = {
                        scope.launch {
                            backStack.removeLastOrNull()
                        }
                    }
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Default.ArrowBack,
                        contentDescription = stringResource(R.string.app_bar_hamburger_menu_content_description)
                    )
                }
            }
        },
        actions = { actions() }
    )
}
