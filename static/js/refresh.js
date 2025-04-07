$(document).ready(function() {
    let countdownValue = 60;
    let countdownInterval;
    let userActive = true;
    
    // Function to reset and start countdown
    function startCountdown() {
        clearInterval(countdownInterval);
        countdownValue = 60;
        $('#countdown').text(countdownValue);
        
        countdownInterval = setInterval(function() {
            if (userActive) {
                countdownValue -= 1;
                $('#countdown').text(countdownValue);
                
                if (countdownValue <= 0) {
                    refreshValueBets();
                    countdownValue = 60;
                }
                
                // Add pulsing effect when countdown is low
                if (countdownValue <= 10) {
                    $('#countdown').parent().addClass('text-danger');
                } else {
                    $('#countdown').parent().removeClass('text-danger');
                }
            }
        }, 1000);
    }
    
    // Function to refresh value bets
    function refreshValueBets() {
        $('#refresh-btn').prop('disabled', true);
        $('#refresh-btn').html('<span class="loading-spinner"></span> Refreshing...');
        $('#refresh-status').html('<span class="loading-spinner"></span> Fetching latest odds...');
        $('#refresh-status').addClass('status-updating');
        
        $.ajax({
            url: '/refresh/',
            type: 'GET',
            success: function(response) {
                $('#refresh-status').html('<i class="fas fa-check-circle me-1"></i> Updated successfully!');
                $('#refresh-status').removeClass('status-updating').addClass('status-success');
                $('#last-update-time').text(response.last_update);
                
                // Show success toast
                showToast('Success', `Updated ${response.count} value bets in ${parseFloat(response.message.match(/\d+\.\d+/)[0]).toFixed(2)} seconds`, 'success');
                
                // Reload the page with a fade effect
                $('body').fadeOut(500, function() {
                    location.reload();
                });
            },
            error: function(xhr, status, error) {
                $('#refresh-btn').prop('disabled', false);
                $('#refresh-btn').html('<i class="fas fa-sync-alt me-2"></i>Refresh Data');
                $('#refresh-status').html('<i class="fas fa-exclamation-circle me-1"></i> Error refreshing data');
                $('#refresh-status').removeClass('status-updating').addClass('status-error');
                
                // Show error toast
                showToast('Error', 'Could not update value bets. Please try again.', 'error');
            }
        });
    }
    
    // Toast notification
    function showToast(title, message, type) {
        // Create toast container if it doesn't exist
        if ($('#toast-container').length === 0) {
            $('body').append('<div id="toast-container" class="position-fixed top-0 end-0 p-3" style="z-index: 1050;"></div>');
        }
        
        // Set toast color based on type
        let bgClass = 'bg-primary';
        let icon = 'info-circle';
        
        if (type === 'success') {
            bgClass = 'bg-success';
            icon = 'check-circle';
        } else if (type === 'error') {
            bgClass = 'bg-danger';
            icon = 'exclamation-circle';
        } else if (type === 'warning') {
            bgClass = 'bg-warning';
            icon = 'exclamation-triangle';
        }
        
        // Create toast
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="3000">
                <div class="toast-header ${bgClass} text-white">
                    <i class="fas fa-${icon} me-2"></i>
                    <strong class="me-auto">${title}</strong>
                    <small>Just now</small>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        // Add toast to container and show it
        $('#toast-container').append(toastHtml);
        const toastElement = new bootstrap.Toast(document.getElementById(toastId));
        toastElement.show();
        
        // Remove toast after it's hidden
        $(`#${toastId}`).on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }
    
    // Manual refresh button
    $('#refresh-btn').click(function() {
        refreshValueBets();
    });
    
    // Track user activity
    function updateUserActivity() {
        userActive = true;
        
        // Reset the activity timeout
        clearTimeout(inactivityTimeout);
        inactivityTimeout = setTimeout(function() {
            userActive = false;
            $('#refresh-status').html('<i class="fas fa-pause-circle me-1"></i> Auto-refresh paused (inactive)');
            $('#refresh-status').removeClass('status-updating status-success').addClass('text-muted');
        }, 5 * 60 * 1000); // 5 minutes of inactivity
    }
    
    // Set up activity tracking
    let inactivityTimeout;
    $(document).on('mousemove click keypress', updateUserActivity);
    
    // Add additional UI enhancements
    
    // Hover effects for bet cards
    $('.value-bet-card').hover(
        function() {
            $(this).addClass('shadow-lg');
        },
        function() {
            $(this).removeClass('shadow-lg');
        }
    );
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize
    updateUserActivity();
    startCountdown();
    
    // Add animation to stats cards
    $('.stats-card').each(function(index) {
        $(this).delay(index * 100).animate({
            opacity: 1,
            top: 0
        }, 500);
    });
}); 