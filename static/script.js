function toggleSidebar() {
    document.getElementById("sidebar").classList.toggle("active");
    document.getElementById("content").classList.toggle("active");

    var settingsButton = document.getElementById("settings-button");

    // Toggle the display property between 'none' and 'block'
    if (settingsButton.style.display === "none") {
        settingsButton.style.display = "block";
    } else {
        settingsButton.style.display = "none";
    }
}

function toggleMap(action) {
    const mapContainer = document.getElementById("map-container");
    const imageUpload = document.getElementById("file-input");
    const analyzeButton = document.getElementById("analyze");
    const downloadButton = document.getElementById("download-image-interactive");
    if (action === 'show') {
        imageUpload.style.display = "none"
        mapContainer.style.display = "flex";
        analyzeButton.style.display = "none";
        downloadButton.style.display = "inline-block";
    } else if (action === 'hide') {
        imageUpload.style.display = "flex"
        mapContainer.style.display = "none";
        analyzeButton.style.display = "inline-block";
        downloadButton.style.display = "none";
    }
}




var map = L.map('map', {
    editable: true // Enable editable on the map
}).setView([48.2082, 16.3738], 13);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

var rectangle;
var bounds;
var labels = [];

function updateLabels() {
    if (!rectangle) return;

    // Remove existing labels
    labels.forEach(function(label) {
        map.removeLayer(label);
    });
    labels = [];

    var latlngs = rectangle.getLatLngs()[0];
    
    for (var i = 0; i < latlngs.length; i++) {
        var pointA = latlngs[i];
        var pointB = latlngs[(i + 1) % latlngs.length];
        
        // Calculate distance in meters
        var distance = map.distance(pointA, pointB);

        // Convert to kilometers if greater than 1000 meters
        var distanceText = distance > 1000 ? (distance / 1000).toFixed(2) + ' km' : distance.toFixed(0) + ' m';

        // Calculate midpoint for label position
        var midPoint = L.latLng(
            (pointA.lat + pointB.lat) / 2,
            (pointA.lng + pointB.lng) / 2
        );

        var labelPosition;
        switch(i) {
            case 0: // Left side
                labelPosition = L.latLng(midPoint.lat, midPoint.lng - 0.009); 
                break;
            case 1: // Top side
                labelPosition = L.latLng(midPoint.lat + 0.0025, midPoint.lng - 0.0035); 
                break;
            case 2: // Rights side
                labelPosition = L.latLng(midPoint.lat, midPoint.lng + 0.00035);
                break;
            case 3: // Bottom side
                labelPosition = L.latLng(midPoint.lat - 0.00035, midPoint.lng - 0.0035); 
                break;
        } 

        var label = L.marker(labelPosition, {
            icon: L.divIcon({
                className: 'distance-label',
                html: distanceText,
                iconSize: null,
                iconAnchor: [0, 0]
            })
        }).addTo(map);

        labels.push(label);
    }
}

map.on('click', function(e) {
    if (rectangle) {
        map.removeLayer(rectangle);
    }

    bounds = [
        [e.latlng.lat - 0.01, e.latlng.lng - 0.01],
        [e.latlng.lat + 0.01, e.latlng.lng + 0.01]
    ];

    rectangle = L.rectangle(bounds, { color: "#ff7800", weight: 1, editable: true }).addTo(map);

    // Enable editing on the rectangle
    rectangle.enableEdit();

    // Update labels initially
    updateLabels();

    // Update labels and bounds during editing
    const updateRectangleBounds = function() {
        bounds = rectangle.getBounds().toBBoxString().split(',');
        bounds = [
            [parseFloat(bounds[1]), parseFloat(bounds[0])],
            [parseFloat(bounds[3]), parseFloat(bounds[2])]
        ];
        updateLabels();
    };

    rectangle.on('editable:dragend editable:vertex:dragend editable:vertex:deleted', updateRectangleBounds);

    // Change the style when editing starts
    rectangle.on('editable:editing', function() {
        rectangle.setStyle({
            color: '#00ff00',  // Green color when editing
            weight: 2,         // Thicker border during editing
            dashArray: '5, 5', // Dashed border
            fillOpacity: 0.2   // Transparent fill
        });
        updateRectangleBounds();
    });

    // Revert back to the original style when editing stops or drawing ends
    const revertStyle = function() {
        rectangle.setStyle({
            color: '#ff7800',   // Original orange color
            weight: 1,          // Original weight
            dashArray: '',      // Solid border
            fillOpacity: 0.2    // Original fill opacity
        });
    };

    rectangle.on('editable:disable', revertStyle);
    rectangle.on('editable:drawing:end', revertStyle);
    rectangle.on('editable:vertex:dragend', revertStyle);
    rectangle.on('editable:dragend', revertStyle);

    // Optionally, disable editing on double-click
    rectangle.on('dblclick', function() {
        rectangle.toggleEdit();
        revertStyle();
    });
});



var socket = io();

$('#file-input').change(function() {
    var file = this.files[0];
    var formData = new FormData();
    formData.append('file', file);

    $('#loading-spinner-input').show();
    $('#input_image').hide();
    $('#error-message').hide();

	showToast("info", "Upload started", "Please wait while image is being uploaded. This might take a while depending on your image size.")

    $.ajax({
        url: '/upload',
        type: 'POST',
        data: formData,
        contentType: false,
        processData: false,
        success: function(data) {
            $('#input_image').attr('src', data.displaypath);
            $('#input_image').data('filepath', data.filepath);
            // Hide the spinner
            $('#loading-spinner-input').hide();
            $('#input_image').show();
			showToast("success", "Successful Upload!", "Image has been uploaded successfully. Start analyzation by clicking the Analyze Image - Button.")
        },
        error: function() {
            // Hide the spinner if there is an error
            $('#loading-spinner-input').hide();
            showToast("error", "Upload Image Error", "Error here")
        }
    });
});

$('#analyze').click(function() {
    var image_path = $('#input_image').data('filepath');
    var model_path = "urban_trees_Cambridge_20230630.pth"; // Update this to your actual model path

    // Show the spinner
    $('#loading-spinner-output').show();
    $('#output_image').hide();
    $('#error-message-ouput').hide();

	showToast("info", "Analyzation started", "Please wait while image is being analysed. This might take a while depending on your image size.")

    $.ajax({
        url: '/evaluate',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ image_path: image_path, model_path: model_path }),
        success: function(data) {
            $('#output_image').attr('src', data.output_image);
            // Hide the spinner
            $('#output_image').show();
            $('#loading-spinner-output').hide();
			showToast("success", "Image successfully analyzed!", "Image has been successfully analyzed. All detected trees have been marked red in the output image.")
        },
        error: function() {
            // Hide the spinner if there is an error
            $('#loading-spinner-output').hide();
            showToast("error", "Analyzing image Error", "Error here")
        }
    });
});

$('#save_settings').click(function() {
    var settings = {
        tiling: {
            buffer: $('#buffer').val(),
            tile_width: $('#tile_width').val(),
            tile_height: $('#tile_height').val()
        },
        crown: {
            confidence: $('#confidence').val()
        }
    };

    $.ajax({
        url: '/save_settings',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(settings),
        success: function() {
            showToast("success", "Settings saved successfully", "")
        }
    });
});

$('#download-image-interactive').click(function() {
    if (!bounds) {
        showToast("warning", "No area selected", "Please select an area on the map.")
        return;
    }

    var coordinates = [
        [bounds[0][0], bounds[0][1]],
        [bounds[1][0], bounds[1][1]],
        [bounds[1][0], bounds[1][1]],
        [bounds[0][0], bounds[1][1]],
        [bounds[0][0], bounds[0][1]]
    ];

    $('#loading-spinner-input').show();
    $('#input_image').hide();
    $('#error-message').hide();

    $.ajax({
        url: '/download_image',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ coordinates: coordinates }),
        success: function(data) {
            $('#input_image').attr('src', data.displaypath);
            $('#input_image').data('filepath', data.filepath);
            // Hide the spinner
            $('#loading-spinner-input').hide();
            $('#input_image').show();
			showToast("success", "Downloaded Area!", "Area has been downloaded successful and will now be analyzed")
            $("#analyze").click();
        },
        error: function() {
            // Hide the spinner if there is an error
            $('#loading-spinner-input').hide();
            $('#error-message').show().delay(5000).fadeOut();
            showToast("error", "Download Area Error", "Error here")
        }
    });
});

function showToast(type, title, message) {
	Swal.fire({
		toast: true,
		position: 'top-end',
		icon: type,
		title: title,
		text: message,
		showConfirmButton: false,
		timer: 3000,
		timerProgressBar: true,
		didOpen: (toast) => {
			toast.addEventListener('mouseenter', Swal.stopTimer);
			toast.addEventListener('mouseleave', Swal.resumeTimer);
		}
	});
}