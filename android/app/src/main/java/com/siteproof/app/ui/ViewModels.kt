package com.siteproof.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.siteproof.app.data.InspectionDetail
import com.siteproof.app.data.InspectionRepository
import com.siteproof.app.data.InspectionSummary
import com.siteproof.app.data.SessionExpiredException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface AuthState {
    data object Idle : AuthState
    data object Loading : AuthState
    data class Error(val message: String) : AuthState
    data object Authenticated : AuthState
}

class AuthViewModel(private val repository: InspectionRepository) : ViewModel() {
    private val _state = MutableStateFlow<AuthState>(if (repository.hasSession()) AuthState.Authenticated else AuthState.Idle)
    val state: StateFlow<AuthState> = _state.asStateFlow()

    fun login(email: String, password: String) {
        if (email.isBlank() || password.length < 8) {
            _state.value = AuthState.Error("Enter a valid email and password.")
            return
        }
        viewModelScope.launch {
            _state.value = AuthState.Loading
            _state.value = try {
                repository.login(email, password)
                AuthState.Authenticated
            } catch (error: Exception) {
                AuthState.Error(error.message ?: "Unable to sign in.")
            }
        }
    }

    fun signOut() {
        repository.signOut()
        _state.value = AuthState.Idle
    }

    fun expireSession() {
        repository.signOut()
        _state.value = AuthState.Idle
    }
}

data class InspectionsState(
    val loading: Boolean = true,
    val items: List<InspectionSummary> = emptyList(),
    val offline: Boolean = false,
    val error: String? = null,
)

class InspectionsViewModel(
    private val repository: InspectionRepository,
    private val onSessionExpired: () -> Unit = {},
) : ViewModel() {
    private val _state = MutableStateFlow(InspectionsState())
    val state: StateFlow<InspectionsState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            _state.value = try {
                val result = repository.loadInspections()
                InspectionsState(loading = false, items = result.items, offline = result.offline)
            } catch (error: SessionExpiredException) {
                onSessionExpired()
                InspectionsState(loading = false)
            } catch (error: Exception) {
                InspectionsState(loading = false, error = error.message ?: "Unable to load inspections.")
            }
        }
    }
}

data class InspectionDetailState(
    val loading: Boolean = true,
    val item: InspectionDetail? = null,
    val offline: Boolean = false,
    val actionInProgress: Boolean = false,
    val error: String? = null,
)

class InspectionDetailViewModel(
    private val repository: InspectionRepository,
    private val inspectionId: String,
    private val onSessionExpired: () -> Unit = {},
) : ViewModel() {
    private val _state = MutableStateFlow(InspectionDetailState())
    val state: StateFlow<InspectionDetailState> = _state.asStateFlow()

    init { load() }

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            _state.value = try {
                val (item, offline) = repository.loadInspection(inspectionId)
                InspectionDetailState(loading = false, item = item, offline = offline)
            } catch (error: SessionExpiredException) {
                onSessionExpired()
                InspectionDetailState(loading = false)
            } catch (error: Exception) {
                InspectionDetailState(loading = false, error = error.message ?: "Unable to load inspection.")
            }
        }
    }

    fun acknowledge() = performAction { repository.acknowledge(inspectionId) }
    fun markReady() = performAction { repository.markReady(inspectionId) }

    private fun performAction(action: suspend () -> InspectionSummary) {
        if (_state.value.offline) {
            _state.value = _state.value.copy(error = "Connect to the network before changing inspection status.")
            return
        }
        viewModelScope.launch {
            _state.value = _state.value.copy(actionInProgress = true, error = null)
            try {
                action()
                val (item, offline) = repository.loadInspection(inspectionId)
                _state.value = InspectionDetailState(loading = false, item = item, offline = offline)
            } catch (error: SessionExpiredException) {
                onSessionExpired()
                _state.value = InspectionDetailState(loading = false)
            } catch (error: Exception) {
                _state.value = _state.value.copy(
                    actionInProgress = false,
                    error = error.message ?: "Unable to update inspection.",
                )
            }
        }
    }
}

class SiteProofViewModelFactory<T : ViewModel>(private val create: () -> T) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <VM : ViewModel> create(modelClass: Class<VM>): VM = create() as VM
}
