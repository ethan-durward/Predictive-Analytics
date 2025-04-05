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
            }
        }, 1000);
    }
    
    // Function to refresh value bets
    function refreshValueBets() {
        $('#refresh-status').text('Refreshing...');
        $('#refresh-btn').prop('disabled', true);
        
        $.ajax({
            url: '/refresh/',
            type: 'GET',
            success: function(response) {
                $('#refresh-status').text('Updated successfully!');
                $('#last-update-time').text(response.last_update);
                
                // Reload the page to show new data
                location.reload();
            },
            error: function() {
                $('#refresh-status').text('Error refreshing data');
                $('#refresh-btn').prop('disabled', false);
            }
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
            $('#refresh-status').text('Auto-refresh paused (inactive)');
        }, 5 * 60 * 1000); // 5 minutes of inactivity
    }
    
    // Set up activity tracking
    let inactivityTimeout;
    $(document).on('mousemove click keypress', updateUserActivity);
    
    // Initialize
    updateUserActivity();
    startCountdown();
}); 