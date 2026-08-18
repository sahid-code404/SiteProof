package com.siteproof.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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

@Composable
fun SiteProofApp() {
    val context = LocalContext.current.applicationContext
    val tokenStore = remember(context) { TokenStore(context) }
    val repository = remember(context, tokenStore) {
        InspectionRepository(
            api = createApi(context, tokenStore),
            tokenStore = tokenStore,
            cache = InspectionCache(context),
        )
    }
    val authViewModel: AuthViewModel = viewModel(
        factory = SiteProofViewModelFactory { AuthViewModel(repository) },
    )
    val authState by authViewModel.state.collectAsStateWithLifecycle()
    val navController = rememberNavController()

    MaterialTheme {
        if (authState !is AuthState.Authenticated) {
            LoginScreen(state = authState, onLogin = authViewModel::login)
        } else {
            NavHost(navController = navController, startDestination = "inspections") {
                composable("inspections") {
                    val inspectionsViewModel: InspectionsViewModel = viewModel(
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
                        key = "inspection-$id",
                        factory = SiteProofViewModelFactory { InspectionDetailViewModel(repository, id) },
                    )
                    val state by detailViewModel.state.collectAsStateWithLifecycle()
                    InspectionDetailScreen(
                        state = state,
                        onBack = { navController.popBackStack() },
                        onRetry = detailViewModel::load,
                        onAcknowledge = detailViewModel::acknowledge,
                        onReady = detailViewModel::markReady,
                    )
                }
            }
        }
    }
}
