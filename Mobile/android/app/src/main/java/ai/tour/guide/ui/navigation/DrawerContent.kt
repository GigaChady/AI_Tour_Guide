package ai.tour.guide.ui.navigation

import ai.tour.guide.R
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp

@Composable
fun DrawerContent(
    selectedRoute: Route?,
    onRouteSelected: (Route) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            modifier = Modifier.padding(16.dp),
            text = stringResource(R.string.navigation_drawer_header),
            color = MaterialTheme.colorScheme.secondary,
            style = MaterialTheme.typography.titleLarge,
        )
        NavigationDrawerItem(
            modifier = Modifier.testTag("drawer_dashboard"),
            label = { Text(stringResource(R.string.navigation_drawer_item_dashboard)) },
            selected = selectedRoute == Route.Dashboard,
            onClick = { onRouteSelected(Route.Dashboard) },
            icon = {
                Icon(
                    imageVector = Icons.Outlined.Place,
                    contentDescription = null
                )
            }
        )
        NavigationDrawerItem(
            modifier = Modifier.testTag("drawer_profile"),
            label = { Text(stringResource(R.string.navigation_drawer_item_profile)) },
            selected = selectedRoute == Route.Profile,
            onClick = { onRouteSelected(Route.Profile) },
            icon = {
                Icon(
                    imageVector = Icons.Outlined.Person,
                    contentDescription = null
                )
            }
        )
        NavigationDrawerItem(
            modifier = Modifier.testTag("drawer_settings"),
            label = { Text(stringResource(R.string.navigation_drawer_item_app_settings)) },
            selected = selectedRoute == Route.Settings,
            onClick = { onRouteSelected(Route.Settings) },
            icon = {
                Icon(
                    imageVector = Icons.Outlined.Settings,
                    contentDescription = null
                )
            }
        )
        HorizontalDivider(modifier = Modifier.padding(16.dp))
    }
}
