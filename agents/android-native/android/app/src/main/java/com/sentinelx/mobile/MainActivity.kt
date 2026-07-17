package com.sentinelx.mobile

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MonitorHeart
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Badge
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sentinelx.mobile.ui.AgentViewModel
import com.sentinelx.mobile.ui.activity.ActivityScreen
import com.sentinelx.mobile.ui.alerts.AlertsScreen
import com.sentinelx.mobile.ui.diagnostics.DiagnosticsScreen
import com.sentinelx.mobile.ui.health.HealthScreen
import com.sentinelx.mobile.ui.home.HomeScreen
import com.sentinelx.mobile.ui.live.LiveMonitorScreen
import com.sentinelx.mobile.ui.login.LoginScreen
import com.sentinelx.mobile.ui.settings.SettingsScreen
import com.sentinelx.mobile.ui.theme.GlassBackground
import com.sentinelx.mobile.ui.theme.SentinelXTheme

private data class Section(val label: String, val icon: ImageVector)

const val SCREEN_HOME = 0
const val SCREEN_LIVE = 1
const val SCREEN_HEALTH = 2
const val SCREEN_ALERTS = 3
const val SCREEN_DIAGNOSTICS = 4
const val SCREEN_ACTIVITY = 5
const val SCREEN_SETTINGS = 6

// Bar/rail destinations capped at Material's 5. Diagnostics and Activity are
// sub-destinations of Settings (also reachable from Home quick actions).
private val NAV_ITEMS = listOf(
    SCREEN_HOME to Section("Home", Icons.Filled.Home),
    SCREEN_LIVE to Section("Live", Icons.Filled.MonitorHeart),
    SCREEN_HEALTH to Section("Health", Icons.Filled.Favorite),
    SCREEN_ALERTS to Section("Alerts", Icons.Filled.NotificationsActive),
    SCREEN_SETTINGS to Section("Settings", Icons.Filled.Settings),
)

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val container = (application as SentinelXApp).container

        setContent {
            val viewModel: AgentViewModel = viewModel(
                factory = AgentViewModel.factory(container, applicationContext)
            )
            val state by viewModel.agentState.collectAsStateWithLifecycle()
            SentinelXTheme(themeMode = state?.themeMode ?: "light") {
                GlassBackground {
                    AppRoot(viewModel)
                }
            }
        }
    }
}

@Composable
private fun AppRoot(viewModel: AgentViewModel) {
    val state by viewModel.agentState.collectAsStateWithLifecycle()

    val current = state
    when {
        current == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }

        // Enrolled agents keep working after the console session ends, so only
        // force the login screen when there is neither a session nor a device.
        !current.isLoggedIn && !current.isEnrolled -> {
            val flags by viewModel.flags.collectAsStateWithLifecycle()
            LoginScreen(
                initialServerUrl = current.baseUrl,
                inProgress = flags.loginInProgress,
                error = flags.loginError,
                onLogin = viewModel::login,
            )
        }

        else -> MainShell(viewModel)
    }
}

@Composable
private fun MainShell(viewModel: AgentViewModel) {
    val state by viewModel.agentState.collectAsStateWithLifecycle()
    val flags by viewModel.flags.collectAsStateWithLifecycle()
    val snapshot by viewModel.snapshot.collectAsStateWithLifecycle()
    val history by viewModel.snapshotHistory.collectAsStateWithLifecycle()
    val health by viewModel.health.collectAsStateWithLifecycle()
    val queueDepth by viewModel.queueDepth.collectAsStateWithLifecycle()
    val alerts by viewModel.alerts.collectAsStateWithLifecycle()
    val diagnostics by viewModel.diagnostics.collectAsStateWithLifecycle()

    var selected by rememberSaveable { mutableIntStateOf(0) }
    var activityFilter by rememberSaveable { mutableStateOf<String?>(null) }

    // Hardware/gesture back walks up the hierarchy instead of exiting
    // (the v1.2.0 Settings fix, generalized to the v2 shell).
    BackHandler(enabled = selected != SCREEN_HOME) {
        selected = when (selected) {
            SCREEN_DIAGNOSTICS, SCREEN_ACTIVITY -> SCREEN_SETTINGS
            else -> SCREEN_HOME
        }
    }

    val context = LocalContext.current
    val notificationPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { _ ->
        // Live Mode is legal without POST_NOTIFICATIONS — the status notification
        // is just suppressed — so a denial must not dead-end the feature.
        viewModel.setLiveMode(true)
    }
    val toggleLive: (Boolean) -> Unit = { enabled ->
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
    }

    val unresolvedAlerts = alerts.count { !it.resolved }
    // Nav rail on wide screens (tablet/foldable/landscape), bottom bar otherwise.
    val wide = LocalConfiguration.current.screenWidthDp >= 840

    val content: @Composable (androidx.compose.foundation.layout.PaddingValues) -> Unit = { padding ->
        Box(Modifier.padding(padding)) {
            val currentState = state ?: return@Box
            when (selected) {
                SCREEN_HOME -> HomeScreen(
                    state = currentState,
                    snapshot = snapshot,
                    history = history,
                    health = health,
                    queueDepth = queueDepth,
                    unresolvedAlerts = unresolvedAlerts,
                    flags = flags,
                    onEnroll = viewModel::enroll,
                    onEnrollWithCode = viewModel::enrollWithCode,
                    onCollectNow = viewModel::collectNow,
                    onUploadNow = viewModel::syncNow,
                    onOpenLive = { selected = SCREEN_LIVE },
                    onOpenHealth = { selected = SCREEN_HEALTH },
                    onOpenDiagnostics = { selected = SCREEN_DIAGNOSTICS },
                )
                SCREEN_LIVE -> {
                    val events by remember { viewModel.eventsFor("monitoring") }
                        .collectAsStateWithLifecycle(emptyList())
                    LiveMonitorScreen(
                        state = currentState,
                        snapshot = snapshot,
                        events = events,
                        onToggleLive = toggleLive,
                        onSetMode = viewModel::setMonitoringMode,
                    )
                }
                SCREEN_HEALTH -> HealthScreen(
                    state = currentState,
                    snapshot = snapshot,
                    history = history,
                    health = health,
                    queueDepth = queueDepth,
                )
                SCREEN_ALERTS -> AlertsScreen(
                    state = currentState,
                    alerts = alerts,
                    flags = flags,
                    onRefresh = viewModel::refreshAlerts,
                    onResolve = viewModel::resolveAlert,
                )
                SCREEN_DIAGNOSTICS -> DiagnosticsScreen(
                    results = diagnostics,
                    flags = flags,
                    onRunAll = viewModel::runDiagnostics,
                )
                SCREEN_ACTIVITY -> {
                    val events by remember(activityFilter) { viewModel.eventsFor(activityFilter) }
                        .collectAsStateWithLifecycle(emptyList())
                    ActivityScreen(
                        events = events,
                        filter = activityFilter,
                        onFilterChange = { activityFilter = it },
                    )
                }
                else -> SettingsScreen(
                    state = currentState,
                    flags = flags,
                    onSetMonitoringMode = viewModel::setMonitoringMode,
                    onSetThemeMode = viewModel::setThemeMode,
                    onSetWifiOnly = viewModel::setWifiOnlyUploads,
                    onSetPauseOnLowBattery = viewModel::setPauseOnLowBattery,
                    onSetReducedMotion = viewModel::setReducedMotion,
                    onTestConnection = viewModel::testConnection,
                    onDeleteLocalData = viewModel::deleteLocalData,
                    onUnenroll = viewModel::unenroll,
                    onLogout = viewModel::logout,
                    onOpenDiagnostics = { selected = SCREEN_DIAGNOSTICS },
                    onOpenActivity = { selected = SCREEN_ACTIVITY },
                )
            }
        }
    }

    if (wide) {
        Row(Modifier.fillMaxSize()) {
            NavigationRail(containerColor = Color.Transparent) {
                NAV_ITEMS.forEach { (screen, section) ->
                    NavigationRailItem(
                        selected = navSelected(screen, selected),
                        onClick = { selected = screen },
                        icon = { SectionIcon(section, screen == SCREEN_ALERTS, unresolvedAlerts) },
                        label = { Text(section.label) },
                    )
                }
            }
            Scaffold(containerColor = Color.Transparent, modifier = Modifier.weight(1f)) { padding -> content(padding) }
        }
    } else {
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = {
                NavigationBar(containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.72f)) {
                    NAV_ITEMS.forEach { (screen, section) ->
                        NavigationBarItem(
                            selected = navSelected(screen, selected),
                            onClick = { selected = screen },
                            icon = { SectionIcon(section, screen == SCREEN_ALERTS, unresolvedAlerts) },
                            label = { Text(section.label, maxLines = 1) },
                        )
                    }
                }
            },
        ) { padding -> content(padding) }
    }
}

// Settings stays highlighted while one of its sub-destinations is open.
private fun navSelected(screen: Int, selected: Int): Boolean =
    selected == screen ||
        (screen == SCREEN_SETTINGS && (selected == SCREEN_DIAGNOSTICS || selected == SCREEN_ACTIVITY))

@Composable
private fun SectionIcon(section: Section, isAlerts: Boolean, unresolvedAlerts: Int) {
    if (isAlerts && unresolvedAlerts > 0) {
        BadgedBox(badge = { Badge { Text("$unresolvedAlerts") } }) {
            Icon(section.icon, contentDescription = section.label)
        }
    } else {
        Icon(section.icon, contentDescription = section.label)
    }
}
