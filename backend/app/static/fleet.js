document.addEventListener('DOMContentLoaded', () => {
    const selectAll = document.getElementById('select-all');
    const deviceSelects = document.querySelectorAll('.device-select');
    const batchActions = document.getElementById('batch-actions');
    const groupLinks = document.querySelectorAll('#group-list .list-group-item');
    const deviceRows = document.querySelectorAll('.device-row');
    
    // Checkbox logic
    function updateBatchActionsVisibility() {
        const checkedCount = document.querySelectorAll('.device-select:checked').length;
        batchActions.style.display = checkedCount > 0 ? 'block' : 'none';
        selectAll.checked = checkedCount === deviceSelects.length && deviceSelects.length > 0;
    }

    selectAll?.addEventListener('change', (e) => {
        const isVisible = row => row.style.display !== 'none';
        deviceSelects.forEach(cb => {
            if (isVisible(cb.closest('tr'))) {
                cb.checked = e.target.checked;
            }
        });
        updateBatchActionsVisibility();
    });

    deviceSelects.forEach(cb => {
        cb.addEventListener('change', updateBatchActionsVisibility);
    });

    // Group filtering
    let currentGroupId = 'all';
    
    groupLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            groupLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            currentGroupId = link.dataset.groupId;
            
            deviceRows.forEach(row => {
                if (currentGroupId === 'all' || row.dataset.groupId === currentGroupId) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                    // uncheck if hidden
                    const cb = row.querySelector('.device-select');
                    if (cb.checked) {
                        cb.checked = false;
                    }
                }
            });
            updateBatchActionsVisibility();
        });
    });

    // Create Group
    document.getElementById('btn-create-group')?.addEventListener('click', () => {
        new bootstrap.Modal(document.getElementById('createGroupModal')).show();
    });

    document.getElementById('submit-create-group')?.addEventListener('click', async () => {
        const form = document.getElementById('create-group-form');
        const data = {
            name: form.name.value,
            description: form.description.value
        };
        
        try {
            const res = await fetch('/api/v1/fleet/groups', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            if (res.ok) {
                location.reload();
            } else {
                const err = await res.json();
                alert('Error creating group: ' + (err.detail || 'Unknown'));
            }
        } catch (err) {
            console.error(err);
        }
    });
    
    // Batch commands
    document.querySelectorAll('.batch-cmd').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (currentGroupId === 'all' || currentGroupId === 'ungrouped') {
                alert('Commands must be sent to a specific group, or we need to assign selected devices to a group first.');
                // For simplicity, let's just use the /api/v1/devices/{id}/commands loop for ungrouped devices
                const selected = Array.from(document.querySelectorAll('.device-select:checked')).map(cb => cb.value);
                if (confirm(`Send ${btn.dataset.cmd} to ${selected.length} devices?`)) {
                    for (const id of selected) {
                        fetch(`/api/v1/devices/${id}/commands`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({command_type: btn.dataset.cmd, payload: {}, confirmed: true})
                        });
                    }
                    alert('Commands queued.');
                    deviceSelects.forEach(cb => cb.checked = false);
                    updateBatchActionsVisibility();
                }
                return;
            }
            
            const cmd = btn.dataset.cmd;
            if (confirm(`Send ${cmd} to group?`)) {
                try {
                    const res = await fetch(`/api/v1/fleet/groups/${currentGroupId}/commands`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            command_type: cmd,
                            payload: {},
                            confirmed: true
                        })
                    });
                    if (res.ok) {
                        alert('Group command dispatched successfully.');
                        deviceSelects.forEach(cb => cb.checked = false);
                        updateBatchActionsVisibility();
                    } else {
                        const err = await res.json();
                        alert('Error dispatching: ' + err.detail);
                    }
                } catch (e) {
                    console.error(e);
                }
            }
        });
    });
});
