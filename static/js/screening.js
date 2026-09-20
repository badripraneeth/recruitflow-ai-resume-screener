/**
 * RecruitFlow - Screening & Candidate Pipeline Interactions
 * Features:
 *  - Dynamic candidate status updates via AJAX (fetch)
 *  - Recruiter Notes quick-save without page reloads
 *  - Bulk candidate selection toolbar with batch shortlist/reject
 *  - Client-side real-time table search & filtering
 */

document.addEventListener('DOMContentLoaded', () => {
  initCandidateDecisionButtons();
  initRecruiterNotesQuickSave();
  initBulkSelectionToolbar();
  initClientSideTableFilter();
});

/* ==========================================================================
   1. Candidate Decision Buttons (Detail & Pipeline)
   ========================================================================== */
function initCandidateDecisionButtons() {
  const decisionButtons = document.querySelectorAll('.btn-decision');
  decisionButtons.forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      const jobId = btn.dataset.jobId;
      const candidateId = btn.dataset.candidateId;
      const newStatus = btn.dataset.status;

      if (!jobId || !candidateId || !newStatus) return;

      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Updating...';

      try {
        const response = await fetch(`/jobs/${jobId}/candidates/${candidateId}/status/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
          },
          body: JSON.stringify({ status: newStatus })
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
          // Update status badge if present
          const badge = document.getElementById(`candidate-status-badge-${candidateId}`) || document.getElementById('candidate-status-badge');
          if (badge) {
            badge.textContent = data.status_display || newStatus;
            badge.className = 'badge ' + (
              newStatus === 'shortlisted' ? 'badge-success' :
              newStatus === 'rejected' ? 'badge-danger' : 'badge-warning'
            );
          }

          // Toggle active/disabled states on button group
          const siblingButtons = btn.closest('.decision-button-group')?.querySelectorAll('.btn-decision') || [];
          siblingButtons.forEach(b => {
            b.disabled = (b.dataset.status === newStatus);
          });

          showToast(`Candidate status set to: ${data.status_display || newStatus}`, 'success');
        } else {
          showToast('Failed to update candidate status.', 'error');
        }
      } catch (err) {
        console.error('Candidate decision error:', err);
        showToast('Network error while updating candidate status.', 'error');
      } finally {
        btn.textContent = originalText;
        // Keep disabled if current status matches
        if (btn.dataset.status === newStatus) {
          btn.disabled = true;
        } else {
          btn.disabled = false;
        }
      }
    });
  });
}

/* ==========================================================================
   2. Recruiter Notes Quick-Save
   ========================================================================== */
function initRecruiterNotesQuickSave() {
  const notesForm = document.getElementById('recruiter-notes-form');
  if (!notesForm) return;

  const notesTextarea = document.getElementById('recruiter-notes-input');
  const saveBtn = document.getElementById('btn-save-notes');
  const jobId = notesForm.dataset.jobId;
  const candidateId = notesForm.dataset.candidateId;

  if (!notesForm || !notesTextarea || !saveBtn) return;

  notesForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const notesContent = notesTextarea.value.trim();

    saveBtn.disabled = true;
    const originalText = saveBtn.textContent;
    saveBtn.textContent = 'Saving...';

    try {
      const response = await fetch(`/jobs/${jobId}/candidates/${candidateId}/notes/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ notes: notesContent })
      });

      if (!response.ok) throw new Error('Failed to save notes');

      const data = await response.json();
      if (data.success) {
        saveBtn.textContent = 'Saved ✓';
        showToast('Recruiter notes saved successfully! ✓', 'success');
        setTimeout(() => {
          saveBtn.textContent = originalText;
          saveBtn.disabled = false;
        }, 2000);
      }
    } catch (err) {
      console.error('Notes save error:', err);
      showToast('Error saving recruiter notes.', 'error');
      saveBtn.textContent = originalText;
      saveBtn.disabled = false;
    }
  });
}

/* ==========================================================================
   3. Bulk Selection & Batch Actions
   ========================================================================== */
function initBulkSelectionToolbar() {
  const selectAllCheckbox = document.getElementById('selectAllCandidates');
  const candidateCheckboxes = document.querySelectorAll('.candidate-select-checkbox');
  const bulkToolbar = document.getElementById('bulk-actions-toolbar');
  const selectedCountSpan = document.getElementById('selected-count');
  const btnBulkShortlist = document.getElementById('btn-bulk-shortlist');
  const btnBulkReject = document.getElementById('btn-bulk-reject');
  const btnClearSelection = document.getElementById('btn-clear-selection');

  if (!selectAllCheckbox && candidateCheckboxes.length === 0) return;

  function getSelectedIds() {
    return Array.from(document.querySelectorAll('.candidate-select-checkbox:checked')).map(cb => cb.value);
  }

  function updateToolbar() {
    const selectedIds = getSelectedIds();
    const count = selectedIds.length;

    if (selectedCountSpan) selectedCountSpan.textContent = count;

    if (bulkToolbar) {
      if (count > 0) {
        bulkToolbar.classList.add('visible');
      } else {
        bulkToolbar.classList.remove('visible');
      }
    }

    if (selectAllCheckbox) {
      selectAllCheckbox.checked = (count > 0 && count === candidateCheckboxes.length);
      selectAllCheckbox.indeterminate = (count > 0 && count < candidateCheckboxes.length);
    }
  }

  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', () => {
      candidateCheckboxes.forEach(cb => {
        // Only select visible rows if filtered
        const row = cb.closest('tr');
        if (!row || row.style.display !== 'none') {
          cb.checked = selectAllCheckbox.checked;
        }
      });
      updateToolbar();
    });
  }

  candidateCheckboxes.forEach(cb => {
    cb.addEventListener('change', updateToolbar);
  });

  if (btnClearSelection) {
    btnClearSelection.addEventListener('click', () => {
      candidateCheckboxes.forEach(cb => { cb.checked = false; });
      if (selectAllCheckbox) selectAllCheckbox.checked = false;
      updateToolbar();
    });
  }

  async function handleBulkAction(endpoint, actionName, badgeClass, newStatusText) {
    const selectedIds = getSelectedIds();
    const jobId = bulkToolbar?.dataset.jobId;

    if (!jobId || selectedIds.length === 0) return;

    const btn = (actionName === 'Shortlist') ? btnBulkShortlist : btnBulkReject;
    if (btn) btn.disabled = true;

    try {
      const response = await fetch(`/jobs/${jobId}/candidates/${endpoint}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ candidate_ids: selectedIds })
      });

      if (!response.ok) throw new Error('Bulk action failed');

      const data = await response.json();
      if (data.success) {
        // Update badges for each selected candidate
        selectedIds.forEach(id => {
          const badge = document.getElementById(`candidate-status-badge-${id}`);
          if (badge) {
            badge.textContent = newStatusText;
            badge.className = `badge ${badgeClass}`;
          }
        });

        showToast(`Successfully ${newStatusText.toLowerCase()} ${selectedIds.length} candidate(s)! ✓`, 'success');

        // Clear checkboxes
        candidateCheckboxes.forEach(cb => { cb.checked = false; });
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        updateToolbar();
      }
    } catch (err) {
      console.error('Bulk action error:', err);
      showToast(`Error executing bulk ${actionName.toLowerCase()}.`, 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  if (btnBulkShortlist) {
    btnBulkShortlist.addEventListener('click', () => {
      handleBulkAction('bulk-shortlist', 'Shortlist', 'badge-success', 'Shortlisted');
    });
  }

  if (btnBulkReject) {
    btnBulkReject.addEventListener('click', () => {
      handleBulkAction('bulk-reject', 'Reject', 'badge-danger', 'Rejected');
    });
  }
}

/* ==========================================================================
   4. Instant Client-Side Table Filter
   ========================================================================== */
function initClientSideTableFilter() {
  const searchInput = document.getElementById('candidateSearchInput');
  const tableBody = document.querySelector('.data-table tbody');
  if (!searchInput || !tableBody) return;

  const rows = tableBody.querySelectorAll('tr[data-candidate-row]');
  if (rows.length === 0) return;

  searchInput.addEventListener('input', (e) => {
    const term = e.target.value.trim().toLowerCase();

    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      if (!term || text.includes(term)) {
        row.style.display = '';
      } else {
        row.style.display = 'none';
      }
    });
  });
}
