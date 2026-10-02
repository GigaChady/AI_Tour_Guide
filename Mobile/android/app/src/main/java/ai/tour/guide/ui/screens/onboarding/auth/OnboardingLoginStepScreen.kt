package ai.tour.guide.ui.screens.onboarding.auth

import ai.tour.guide.R
import ai.tour.guide.ui.components.onboarding.LoadingOverlay
import ai.tour.guide.ui.components.onboarding.OnboardingWelcomeText
import ai.tour.guide.ui.components.shared.ToastOnRequestError
import ai.tour.guide.ui.navigation.Route
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation3.runtime.NavBackStack
import androidx.navigation3.runtime.NavKey
import org.koin.compose.viewmodel.koinViewModel

@Preview(showBackground = true)
@Composable
fun OnboardingLoginStepScreen(
    modifier: Modifier = Modifier,
    viewModel: OnboardingAuthStepViewModel = koinViewModel(),
    backStack: NavBackStack<NavKey>? = null
) {
    val context = LocalContext.current
    val viewModelState by viewModel.viewStateFlow.collectAsStateWithLifecycle()

    LifecycleStartEffect(viewModelState.isSuccess) {
        if (viewModelState.isSuccess) {
            backStack?.clear()
            backStack?.add(Route.OnboardingPreferencesStepScreen)
        }
        onStopOrDispose { }
    }

    ToastOnRequestError(viewModel = viewModel)
    Surface(
        modifier = modifier
            .fillMaxSize()
            .testTag("onboarding_login_screen"),
        color = MaterialTheme.colorScheme.background
    ) {
        Box(modifier = Modifier.fillMaxSize()) {
            Column {
                OnboardingWelcomeText(stringResource(R.string.onboarding_step2_header_text_body))
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 32.dp, vertical = 16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    OutlinedTextField(
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("login_email_input"),
                        value = viewModelState.data.email,
                        onValueChange = { viewModel.onEmailChanged(it) },
                        label = { Text(stringResource(R.string.onboarding_step2_email_input_title)) }
                    )
                    OutlinedTextField(
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("login_password_input"),
                        value = viewModelState.data.password,
                        onValueChange = { viewModel.onPasswordChanged(it) },
                        visualTransformation = PasswordVisualTransformation(),
                        label = { Text(stringResource(R.string.onboarding_step2_password_input_title)) }
                    )
                    RegisterLink(
                        onClick = {
                            backStack?.add(Route.OnboardingRegisterStepScreen)
                        }
                    )
                }
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 32.dp, vertical = 16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Button(
                        onClick = { viewModel.onLoginClicked() },
                        enabled = !viewModelState.isLoading,
                        shape = MaterialTheme.shapes.large,
                        modifier = Modifier.fillMaxWidth(0.8f)
                    ) {
                        Icon(Icons.Default.AccountCircle, null)
                        Text(stringResource(R.string.onboarding_step2_login_button))
                    }
                    HorizontalDivider(modifier = Modifier.fillMaxWidth(0.6f))
                    OutlinedButton(
                        onClick = { viewModel.onSignInWithGoogleClicked(context) },
                        enabled = !viewModelState.isLoading,
                        shape = MaterialTheme.shapes.large,
                        modifier = Modifier.fillMaxWidth(0.8f)
                    ) {
                        Icon(
                            painter = painterResource(id = R.drawable.ic_google_logo),
                            contentDescription = "Google Logo",
                            modifier = Modifier.size(24.dp),
                            tint = Color.Unspecified
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(stringResource(R.string.onboarding_step2_login_with_google_button))
                    }
                }
            }

            LoadingOverlay(isVisible = viewModelState.isLoading)
        }
    }
}

@Composable
fun RegisterLink(onClick: () -> Unit) {
    val registerLinkText = buildAnnotatedString {
        append(stringResource(R.string.onboarding_step2_no_account_question))
        append(" ")
        withStyle(SpanStyle(color = MaterialTheme.colorScheme.primary)) {
            append(stringResource(R.string.onboarding_step2_register_span))
        }
    }
    Text(
        modifier = Modifier
            .testTag("login_sign_up")
            .clickable { onClick() },
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurface,
        text = registerLinkText
    )
}
