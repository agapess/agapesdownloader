document.addEventListener('DOMContentLoaded', function() {
    const urlInput = document.getElementById('url');
    const urlFeedback = document.getElementById('url-feedback');
    const platformIcon = document.getElementById('platform-icon');
    const downloadForm = document.getElementById('download-form');
    const downloadBtn = document.getElementById('download-btn');
    const downloadProgress = document.getElementById('download-progress');
    const progressText = document.getElementById('progress-text');

    // Handle alert auto-dismissal
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            // Create a Bootstrap alert instance and hide it
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 8000); // Auto-dismiss after 8 seconds
    });

    // Update the platform icon and feedback based on URL input
    urlInput.addEventListener('input', debounce(function() {
        const url = urlInput.value.trim();
        
        if (!url) {
            resetUrlFeedback();
            return;
        }
        
        // Basic URL validation
        if (!isValidUrl(url)) {
            setInvalidFeedback('Invalid URL format');
            return;
        }
        
        // Check which platform the URL belongs to
        checkPlatform(url);
    }, 500));
    
    // Show progress indicator when form is submitted
    downloadForm.addEventListener('submit', function(e) {
        const url = urlInput.value.trim();
        
        if (!url) {
            e.preventDefault();
            setInvalidFeedback('Please enter a video URL');
            return;
        }
        
        if (!isValidUrl(url)) {
            e.preventDefault();
            setInvalidFeedback('Invalid URL format');
            return;
        }
        
        // Determine platform for customized message
        let platform = '';
        if (url.includes('youtube') || url.includes('youtu.be')) {
            platform = 'YouTube';
        } else if (url.includes('instagram')) {
            platform = 'Instagram';
        } else if (url.includes('twitter') || url.includes('x.com')) {
            platform = 'Twitter/X';
        } else {
            platform = 'video';
        }
        
        // Show download progress indicator with customized message
        progressText.textContent = `Please wait while we process your ${platform} video...`;
        downloadProgress.style.display = 'block';
        downloadBtn.disabled = true;
        
        // Scroll to the progress indicator
        setTimeout(() => {
            downloadProgress.scrollIntoView({behavior: 'smooth'});
        }, 100);
    });
    
    // Helper function to validate URL format
    function isValidUrl(url) {
        try {
            new URL(url);
            return true;
        } catch (e) {
            return false;
        }
    }
    
    // Function to check which platform the URL belongs to via AJAX
    function checkPlatform(url) {
        fetch('/ajax/platform-check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url: url })
        })
        .then(response => response.json())
        .then(data => {
            if (data.valid) {
                if (data.platform) {
                    setValidFeedback(`Valid ${data.platform.charAt(0).toUpperCase() + data.platform.slice(1)} URL`);
                    updatePlatformIcon(data.platform);
                    // Enable button and add platform class
                    downloadBtn.disabled = false;
                    downloadBtn.classList.remove('btn-secondary', 'btn-primary', 'btn-danger', 'btn-info');
                    
                    // Apply appropriate color based on platform
                    switch (data.platform) {
                        case 'youtube':
                            downloadBtn.classList.add('btn-danger');
                            break;
                        case 'instagram':
                            downloadBtn.classList.add('btn-primary');
                            break;
                        case 'twitter':
                            downloadBtn.classList.add('btn-info');
                            break;
                        default:
                            downloadBtn.classList.add('btn-primary');
                    }
                } else {
                    setInvalidFeedback('Unsupported platform. Please use YouTube, Instagram, or Twitter/X');
                    resetPlatformIcon();
                    downloadBtn.disabled = true;
                    downloadBtn.classList.remove('btn-danger', 'btn-primary', 'btn-info');
                    downloadBtn.classList.add('btn-secondary');
                }
            } else {
                setInvalidFeedback('Invalid URL format');
                resetPlatformIcon();
                downloadBtn.disabled = true;
                downloadBtn.classList.remove('btn-danger', 'btn-primary', 'btn-info');
                downloadBtn.classList.add('btn-secondary');
            }
        })
        .catch(error => {
            console.error('Error checking platform:', error);
            setInvalidFeedback('Error checking URL. Please try again.');
            resetPlatformIcon();
            downloadBtn.disabled = true;
            downloadBtn.classList.remove('btn-danger', 'btn-primary', 'btn-info');
            downloadBtn.classList.add('btn-secondary');
        });
    }
    
    // Update the platform icon based on the detected platform
    function updatePlatformIcon(platform) {
        platformIcon.innerHTML = '';
        
        let icon;
        switch (platform) {
            case 'youtube':
                icon = document.createElement('i');
                icon.className = 'fab fa-youtube platform-icon-youtube';
                break;
            case 'instagram':
                icon = document.createElement('i');
                icon.className = 'fab fa-instagram platform-icon-instagram';
                break;
            case 'twitter':
                icon = document.createElement('i');
                icon.className = 'fab fa-twitter platform-icon-twitter';
                break;
            default:
                icon = document.createElement('i');
                icon.className = 'fas fa-link';
        }
        
        platformIcon.appendChild(icon);
    }
    
    // Reset the platform icon to default
    function resetPlatformIcon() {
        platformIcon.innerHTML = '<i class="fas fa-link"></i>';
    }
    
    // Set valid feedback message
    function setValidFeedback(message) {
        urlFeedback.textContent = message;
        urlFeedback.className = 'form-text url-valid';
    }
    
    // Set invalid feedback message
    function setInvalidFeedback(message) {
        urlFeedback.textContent = message;
        urlFeedback.className = 'form-text url-invalid';
    }
    
    // Reset feedback to default state
    function resetUrlFeedback() {
        urlFeedback.textContent = 'Enter a valid video URL from YouTube, Instagram, or Twitter/X';
        urlFeedback.className = 'form-text';
        resetPlatformIcon();
        downloadBtn.disabled = true;
        downloadBtn.classList.remove('btn-danger', 'btn-primary', 'btn-info');
        downloadBtn.classList.add('btn-secondary');
    }
    
    // Debounce function to limit how often the input handler fires
    function debounce(func, wait) {
        let timeout;
        return function() {
            const context = this;
            const args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                func.apply(context, args);
            }, wait);
        };
    }
});
