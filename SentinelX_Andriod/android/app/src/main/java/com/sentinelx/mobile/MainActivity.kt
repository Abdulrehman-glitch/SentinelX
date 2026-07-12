package com.sentinelx.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sentinelx.mobile.ui.AgentViewModel
import com.sentinelx.mobile.ui.dashboard.DashboardScreen
import com.sentinelx.mobile.ui.login.LoginScreen
import com.sentinelx.mobile.ui.settings.SettingsScreen
import com.sentinelx.mobile.ui.theme.GlassBackground
import com.sentinelx.mobile.ui.theme.SentinelXTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val container = (application as SentinelXApp).container

        setContent {
            SentinelXTheme {
                GlassBackground {
                    val viewModel: AgentViewModel = viewModel(
                        factory = AgentViewModel.factory(container, applicationContext)
                    )
                    AppRoot(viewModel)
                }
            }
        }
    }
}

@Composable
private fun AppRoot(viewModel: AgentViewModel) {
    val state by viewModel.agentState.collectAsStateWithLifecycle()
    val flags by viewModel.flags.collectAsStateWithLifecycle()
    val snapshot by viewModel.snapshot.collectAsStateWithLifecycle()
    val queueDepth by viewModel.queueDepth.collectAsStateWithLifecycle()
    var showSettings by rememberSaveable { mutableStateOf(false) }

    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { _ ->
        // Live Mode is legal without POST_NOTIFICATIONS — the status notification
        // is just suppressed — so a denial must not dead-end the feature.
        viewModel.setLiveMode(true)
    }

    val current = state
    when {
        current == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }

        // Enrolled agents keep working after the console session ends, so only
        // force the login screen when there is neither a session nor a device.
        !current.isLoggedIn && !current.isEnrolled -> LoginScreen(
            initialServerUrl = current.baseUrl,
            inProgress = flags.loginInProgress,
            error = flags.loginError,
            onLogin = viewModel::login,
        )

        showSettings -> SettingsScreen(
            state = current,
            flags = flags,
            onSetInterval = viewModel::setLiveInterval,
            onTestConnection = viewModel::testConnection,
            onUnenroll = {
                viewModel.unenroll()
                showSettings = false
            },
            onLogout = {
                viewModel.logout()
                showSettings = false
            },
            onBack = { showSettings = false },
        )

        else -> {
            val context = androidx.compose.ui.platform.LocalContext.current
            DashboardScreen(
                state = current,
                snapshot = snapshot,
                queueDepth = queueDepth,
                flags = flags,
                onEnroll = viewModel::enroll,
                onSyncNow = viewModel::syncNow,
                onToggleLive = { enabled ->
                    if (!enabled) {
                        viewModel.setLiveMode(false)
                    } else if (
                        Build.VERSION.SDK_INT >= 33 &&
                        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
                        PackageManager.PERMISSION_GRANTED
                    ) {
                        notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    } else {
                        viewModel.setLiveMode(true)
                    }
                },
                onOpenSettings = { showSettings = true },
            )
        }
    }
}
