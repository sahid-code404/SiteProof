package com.siteproof.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.siteproof.app.data.InspectionCache
import com.siteproof.app.data.InspectionRepository
import com.siteproof.app.data.TokenStore
import com.siteproof.app.data.createApi
import com.siteproof.app.verification.VerificationCaptureCoordinator
import com.siteproof.app.verification.VerificationRepository
import com.siteproof.app.verification.VerificationScreen
import com.siteproof.app.verification.VerificationViewModel
import com.siteproof.app.verification.db.PendingEvidenceDatabase
import com.siteproof.app.verification.upload.EvidenceUploadWorker

@Composable
fun SiteProofApp() {
    val context = LocalContext.current.applicationContext
    val tokenStore = remember(context) { TokenStore(context) }
    val api = remember(context, tokenStore) { createApi(context, tokenStore) }
    val repository = remember(context, tokenStore, api) {
        InspectionRepository(
            api = api,
            tokenStore = tokenStore,
            cache = InspectionCache(context),
        )
    }
    val verificationRepository = remember(context, api) {
        val database = PendingEvidenceDatabase.get(context)
        VerificationRepository(
            api = api,
            pendingDao = database.pendingEvidenceDao(),
            challengeDao = database.activeChallengeDao(),
        )
    }
    val authViewModel: AuthViewModel = viewModel(
        factory = SiteProofViewModelFactory { AuthViewModel(repository) },
    )
    val authState by authViewModel.state.collectAsStateWithLifecycle()

    MaterialTheme {
        if (authState !is AuthState.Authenticated) {
            LoginScreen(state = authState, onLogin = authViewModel::login)
        } else {
            val sessionScopeKey = repository.sessionScopeKey()
            key(sessionScopeKey) {
                val navController = rememberNavController()
                NavHost(navController = navController, startDestination = "inspections") {
                    composable("inspections") {
                        val inspectionsViewModel: InspectionsViewModel = viewModel(
                            key = "inspections-$sessionScopeKey",
                            factory = SiteProofViewModelFactory { InspectionsViewModel(repository) },
                        )
                        val state by inspectionsViewModel.state.collectAsStateWithLifecycle()
                        InspectionListScreen(
                            inspectorName = repository.inspectorName(),
                            state = state,
                            onRefresh = inspectionsViewModel::refresh,
                            onOpen = { id -> navController.navigate("inspection/$id") },
                            onSignOut = authViewModel::signOut,
                        )
                    }
                    composable(
                        route = "inspection/{id}",
                        arguments = listOf(navArgument("id") { type = NavType.StringType }),
                    ) { backStackEntry ->
                        val id = requireNotNull(backStackEntry.arguments?.getString("id"))
                        val detailViewModel: InspectionDetailViewModel = viewModel(
                            key = "inspection-$sessionScopeKey-$id",
                            factory = SiteProofViewModelFactory { InspectionDetailViewModel(repository, id) },
                        )
                        val state by detailViewModel.state.collectAsStateWithLifecycle()
                        InspectionDetailScreen(
                            state = state,
                            onBack = { navController.popBackStack() },
                            onRetry = detailViewModel::load,
                            onAcknowledge = detailViewModel::acknowledge,
                            onReady = detailViewModel::markReady,
                            onStartVerification = { navController.navigate("verification/$id") },
                        )
                    }
                    composable(
                        route = "verification/{id}",
                        arguments = listOf(navArgument("id") { type = NavType.StringType }),
                    ) { backStackEntry ->
                        val id = requireNotNull(backStackEntry.arguments?.getString("id"))
                        val verificationViewModel: VerificationViewModel = viewModel(
                            key = "verification-$sessionScopeKey-$id",
                            factory = SiteProofViewModelFactory {
                                val coordinator = VerificationCaptureCoordinator(context, verificationRepository)
                                VerificationViewModel(
                                    inspectionId = id,
                                    coordinator = coordinator,
                                    repository = verificationRepository,
                                    enqueueUpload = { sessionId -> EvidenceUploadWorker.enqueue(context, sessionId) },
                                )
                            },
                        )
                        VerificationScreen(
                            viewModel = verificationViewModel,
                            onBack = { navController.popBackStack() },
                        )
                    }
                }
            }
        }
    }
}
