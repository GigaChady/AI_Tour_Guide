package ai.tour.guide.ui.sharedFragments

import ai.tour.guide.R
import ai.tour.guide.ui.components.shared.ToastOnRequestError
import ai.tour.guide.ui.screens.onboarding.auth.OnboardingAuthStepViewModel
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import org.koin.compose.viewmodel.koinViewModel

@Preview(showBackground = true)
@Composable
fun UserRegistrationFragment(
    modifier: Modifier = Modifier,
    onChangesSaved: () -> Unit = {},
    viewModel: OnboardingAuthStepViewModel = koinViewModel(),
    ctaButtonText: String? = null
) {
    val viewModelState by viewModel.viewStateFlow.collectAsStateWithLifecycle()

    LifecycleStartEffect(viewModelState.isSuccess) {
        if (viewModelState.isSuccess) {
            onChangesSaved()
        }
        onStopOrDispose { }
    }

    ToastOnRequestError(viewModel = viewModel)
    Column(modifier = modifier) {
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
                    .testTag("registration_name_input"),
                value = viewModelState.data.name,
                onValueChange = { viewModel.onNameChanged(it) },
                label = { Text(stringResource(R.string.onboarding_step3_name_input_title)) }
            )
            OutlinedTextField(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("registration_email_input"),
                value = viewModelState.data.email,
                onValueChange = { viewModel.onEmailChanged(it) },
                label = { Text(stringResource(R.string.onboarding_step3_email_input_title)) }
            )
            OutlinedTextField(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("registration_password_input"),
                value = viewModelState.data.password,
                visualTransformation = PasswordVisualTransformation(),
                onValueChange = { viewModel.onPasswordChanged(it) },
                label = { Text(stringResource(R.string.onboarding_step3_password_input_title)) }
            )
            OutlinedTextField(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("registration_confirm_password_input"),
                value = viewModelState.data.confirmPassword,
                visualTransformation = PasswordVisualTransformation(),
                onValueChange = { viewModel.onConfirmPasswordChanged(it) },
                label = { Text(stringResource(R.string.onboarding_step3_confirm_password_input_title)) }
            )
        }
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 32.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Button(
                onClick = { viewModel.onRegisterClicked() },
                shape = MaterialTheme.shapes.large,
                modifier = Modifier
                    .fillMaxWidth(0.8f)
                    .testTag("registration_submit")
            ) {
                Icon(Icons.Default.Check, null)
                if (ctaButtonText != null) {
                    Text(ctaButtonText)
                }
            }
        }
    }
}
