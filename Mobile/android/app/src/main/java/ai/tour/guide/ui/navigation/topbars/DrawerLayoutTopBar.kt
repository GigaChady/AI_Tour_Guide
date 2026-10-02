package ai.tour.guide.ui.navigation.topbars

import ai.tour.guide.R
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.DrawerState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DrawerLayoutTopBar(
    drawerState: DrawerState,
    routeTitle: String,
) {
    val scope = rememberCoroutineScope()
    CenterAlignedTopAppBar(
        title = {
            Text(
                text = routeTitle
            )
        },
        navigationIcon = {
            IconButton(
                modifier = Modifier.testTag("app_menu"),
                onClick = {
                    scope.launch {
                        if (drawerState.isClosed) {
                            drawerState.open()
                        } else {
                            drawerState.close()
                        }
                    }
                }
            ) {
                Icon(
                    imageVector = Icons.Default.Menu,
                    contentDescription = stringResource(R.string.app_bar_hamburger_menu_content_description)
                )
            }
        }
    )
}
