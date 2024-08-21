// Toggles the sidebar visibility and adjusts the content area accordingly
function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const content = document.getElementById("content");
    const settingsButton = document.getElementById("settings-button");

    sidebar.classList.toggle("active");
    content.classList.toggle("active");

    // Toggle the settings button display between 'none' and 'block'
    settingsButton.style.display = (settingsButton.style.display === "none") ? "block" : "none";
}

// Toggles the map view and associated UI elements based on the action parameter
function toggleMap(action) {
    const mapContainer = document.getElementById("map-container");
    const mapDatePicker = document.getElementById("map-date-picker");
    const imageDatePicker = document.getElementById("image-date-picker");
    const imageUpload = document.getElementById("file-input");
    const analyzeButton = document.getElementById("analyze");
    const downloadButton = document.getElementById("download-image-interactive");

    if (action === 'show') {
        imageUpload.style.display = "none";
        imageDatePicker.style.display = "none";
        mapContainer.style.display = "flex";
        mapDatePicker.style.display = "flex";
        analyzeButton.style.display = "none";
        downloadButton.style.display = "inline-block";
    } else if (action === 'hide') {
        imageUpload.style.display = "flex";
        imageDatePicker.style.display = "inline-block";
        mapContainer.style.display = "none";
        mapDatePicker.style.display = "none";
        analyzeButton.style.display = "inline-block";
        downloadButton.style.display = "none";
    }
}

// Initialize the map with editable capabilities and set the initial view
const map = L.map('map', {
    editable: true
}).setView([48.2082, 16.3738], 13);

// Add OpenStreetMap tile layer to the map
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
}).addTo(map);

let rectangle;
let bounds;
let labels = [];

// Updates the distance labels on the map
function updateLabels() {
    if (!rectangle) return;

    // Remove existing labels
    labels.forEach(label => map.removeLayer(label));
    labels = [];

    const latlngs = rectangle.getLatLngs()[0];

    latlngs.forEach((pointA, i) => {
        const pointB = latlngs[(i + 1) % latlngs.length];

        // Calculate the distance between two points
        const distance = map.distance(pointA, pointB);
        const distanceText = distance > 1000 ? (distance / 1000).toFixed(2) + ' km' : distance.toFixed(0) + ' m';

        // Calculate the midpoint for label positioning
        const midPoint = L.latLng(
            (pointA.lat + pointB.lat) / 2,
            (pointA.lng + pointB.lng) / 2
        );

        let labelPosition;
        switch (i) {
            case 0: // Left side
                labelPosition = L.latLng(midPoint.lat, midPoint.lng - 0.009);
                break;
            case 1: // Top side
                labelPosition = L.latLng(midPoint.lat + 0.0025, midPoint.lng - 0.0035);
                break;
            case 2: // Right side
                labelPosition = L.latLng(midPoint.lat, midPoint.lng + 0.00035);
                break;
            case 3: // Bottom side
                labelPosition = L.latLng(midPoint.lat - 0.00035, midPoint.lng - 0.0035);
                break;
        }

        const label = L.marker(labelPosition, {
            icon: L.divIcon({
                className: 'distance-label',
                html: distanceText,
                iconSize: null,
                iconAnchor: [0, 0]
            })
        }).addTo(map);

        labels.push(label);
    });
}

// Handles map click events to create and edit a rectangle
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
    const updateRectangleBounds = () => {
        bounds = rectangle.getBounds().toBBoxString().split(',').map(parseFloat);
        bounds = [
            [bounds[1], bounds[0]],
            [bounds[3], bounds[2]]
        ];
        updateLabels();
    };

    rectangle.on('editable:dragend editable:vertex:dragend editable:vertex:deleted', updateRectangleBounds);

    // Change the style when editing starts
    rectangle.on('editable:editing', () => {
        rectangle.setStyle({
            color: '#00ff00',  // Green color when editing
            weight: 2,         // Thicker border during editing
            dashArray: '5, 5', // Dashed border
            fillOpacity: 0.2   // Transparent fill
        });
        updateRectangleBounds();
    });

    // Revert back to the original style when editing stops or drawing ends
    const revertStyle = () => {
        rectangle.setStyle({
            color: '#ff7800',   // Original orange color
            weight: 1,          // Original weight
            dashArray: '',      // Solid border
            fillOpacity: 0.2    // Original fill opacity
        });
    };

    rectangle.on('editable:disable editable:drawing:end editable:vertex:dragend editable:dragend', revertStyle);

    // Optionally, disable editing on double-click
    rectangle.on('dblclick', function() {
        rectangle.toggleEdit();
        revertStyle();
    });
});

// Handles the image file input change event
$('#file-input').change(function() {
    const file = this.files[0];
    const inputDate = $('#image-date').val();

    // Check if a date has been selected
    if (!inputDate) {
        showToast("warning", "No Date Selected", "Please select a date before uploading the image.");
        $(this).val('');  // Clear the file input field
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('input_date', inputDate);

    $('#loading-spinner-input').show();
    $('#input_image').hide();
    $('#error-message').hide();

    showToast("info", "Upload started", "Please wait while image is being uploaded. This might take a while depending on your image size.");

    $.ajax({
        url: '/upload',
        type: 'POST',
        data: formData,
        contentType: false,
        processData: false,
        success: function(data) {
            $('#input_image').attr('src', data.displaypath).data('filepath', data.filepath);
            $('#loading-spinner-input').hide();
            $('#input_image').show();
            showToast("success", "Successful Upload!", "Image has been uploaded successfully. Start analysis by clicking the Analyze Image button.");
        },
        error: function(error) {
            $('#loading-spinner-input').hide();
            showToast("error", "Upload Image Error", error.responseJSON.message);
        }
    });
});

// Calculates the total number of tiles needed for analysis
function calculateTiles() {
    return new Promise((resolve, reject) => {
        $.ajax({
            url: '/calculate-tiles',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ file: $('#input_image').data('filepath') }),
            success: function(data) {
                resolve(data.total_tiles);  // Resolve the Promise with the total tiles
            },
            error: function(error) {
                showToast("error", "Calculating Tiles Error", error.responseJSON.message);
                reject(error);  // Reject the Promise with the error
            }
        });
    });
}

// Shows a modal to confirm tile analysis
async function showTilesModal() {
    try {
        const totalTiles = await calculateTiles();

        // Display SweetAlert modal to the user
        Swal.fire({
            title: `Start analysis with ${totalTiles} tiles?`,
            text: "Up to 50 tiles are recommended for optimal performance (Analysis < 30 minutes). You can increase the tile size to reduce the total number of tiles in the settings.",
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Yes, start analysis',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                startAnalysis();
            } else {
                showToast('info', 'Analysis Cancelled', 'The analysis process was cancelled by the user.');
            }
        });
    } catch (error) {
        console.error('Error:', error);
    }
}

// Trigger analysis modal on analyze button click
$('#analyze').click(function() {
    showTilesModal();
});

// Starts the image analysis process
function startAnalysis() {
    const imagePath = $('#input_image').data('filepath');
    const modelPath = "urban_trees_Cambridge_20230630.pth"; // Update this to your actual model path

    const ndviTable = document.getElementById('ndvi-table');
    const eviTable = document.getElementById('evi-table');
    const gndviTable = document.getElementById('gndvi-table');
    const cigreenTable = document.getElementById('cigreen-table');
    const ciredgeTable = document.getElementById('cired-edge-table');
    const combinedTable = document.getElementById('combined-table');

    $('#loading-spinner-output').show();
    $('#output_image').hide();
    $('#ndvi-values').hide();
    $('#evi-values').hide();
    $('#gndvi-values').hide();
    $('#cigreen-values').hide();
    $('#cired-edge-values').hide();
    $('#combined-values').hide();
    $('#error-message-ouput').hide();

    showToast("info", "Analyzation started", "Please wait while image is being analyzed. This might take a while depending on your image size.");

    $.ajax({
        url: '/evaluate',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ image_path: imagePath, model_path: modelPath }),
        success: function(data) {
            console.log(data);
            $('#output_image').attr('src', data.output_image);

            // NDVI
            $('#ndvi_image').attr('src', data.vi_images.ndvi);
            insertStatsIntoTable(ndviTable, data.vi_stats.ndvi);

            // EVI
            $('#evi_image').attr('src', data.vi_images.evi);
            insertStatsIntoTable(eviTable, data.vi_stats.evi);

            // GNDVI
            $('#gndvi_image').attr('src', data.vi_images.gndvi);
            insertStatsIntoTable(gndviTable, data.vi_stats.gndvi);

            // Chlorophyll Index Green
            $('#cigreen_image').attr('src', data.vi_images.cigreen);
            insertStatsIntoTable(cigreenTable, data.vi_stats.cigreen);

            // Chlorophyll Index Red-Edge
            $('#cired-edge_image').attr('src', data.vi_images['cired-edge']);
            insertStatsIntoTable(ciredgeTable, data.vi_stats['cired-edge']);

            // Combined Index
            $('#combined_image').attr('src', data.vi_images.combined);
            insertStatsIntoTable(combinedTable, data.vi_stats.combined);

            $('#output_image').show();
            $('#ndvi-values').css('display', 'flex').show();
            $('#evi-values').css('display', 'flex').show();
            $('#gndvi-values').css('display', 'flex').show();
            $('#cigreen-values').css('display', 'flex').show();
            $('#cired-edge-values').css('display', 'flex').show();
            $('#combined-values').css('display', 'flex').show();
            $('#loading-spinner-output').hide();

            showToast("success", "Image successfully analyzed!", "Image has been successfully analyzed. All detected trees have been marked red in the output image.");
        },
        error: function(error) {
            $('#loading-spinner-output').hide();
            showToast("error", "Analyzing image Error", error.responseJSON.message);
        }
    });
}

function insertStatsIntoTable(table, stats) {
    table.innerHTML = ""; // Clear the table before inserting new rows
    const headerRow = table.insertRow();
    const headerCell1 = headerRow.insertCell(0);
    const headerCell2 = headerRow.insertCell(1);
    headerCell1.innerText = "Title";
    headerCell2.innerText = "Value";
    for (const [key, value] of Object.entries(stats)) {
        const row = table.insertRow();
        const cell1 = row.insertCell(0);
        const cell2 = row.insertCell(1);
        cell1.innerText = key;
        cell2.innerText = value;
    }
}


function insertStatsIntoTable(table, stats) {
    table.innerHTML = ""; // Clear the table before inserting new rows
    const headerRow = table.insertRow();
    const headerCell1 = headerRow.insertCell(0);
    const headerCell2 = headerRow.insertCell(1);
    headerCell1.innerText = "Title";
    headerCell2.innerText = "Value";
    for (const [key, value] of Object.entries(stats)) {
        const row = table.insertRow();
        const cell1 = row.insertCell(0);
        const cell2 = row.insertCell(1);
        cell1.innerText = key;
        cell2.innerText = value;
    }
}


// Saves user settings for tiling, crown confidence, and VI weights
$('#save_settings').click(function() {
    const ndviWeight = parseFloat($('#ndvi_weight').val());
    const eviWeight = parseFloat($('#evi_weight').val());
    const gndviWeight = parseFloat($('#gndvi_weight').val());
    const cigreenWeight = parseFloat($('#cigreen_weight').val());
    const ciredgeWeight = parseFloat($('#ciredge_weight').val());

    const totalWeight = ndviWeight + eviWeight + gndviWeight + cigreenWeight + ciredgeWeight;

    if (totalWeight !== 1) {
        showToast("error", "Weighting Error", "The sum of the weights must equal 1. Please adjust the weights.");
        return;
    }

    const settings = {
        tiling: {
            buffer: $('#buffer').val(),
            tile_width: $('#tile_width').val(),
            tile_height: $('#tile_height').val()
        },
        crown: {
            confidence: $('#confidence').val()
        },
        vi_weights: {
            ndvi: ndviWeight,
            evi: eviWeight,
            gndvi: gndviWeight,
            cigreen: cigreenWeight,
            ciredge: ciredgeWeight
        }
    };

    $.ajax({
        url: '/save_settings',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(settings),
        success: function() {
            showToast("success", "Settings saved successfully", "");
        },
        error: function(error) {
            showToast("error", "Settings could not be saved.", error.responseJSON.message);
        }
    });
});


// Handles the download of the selected area image
$('#download-image-interactive').click(function() {
    if (!bounds) {
        showToast("warning", "No area selected", "Please select an area on the map.");
        return;
    }

    const coordinates = [
        [bounds[0][0], bounds[0][1]],
        [bounds[1][0], bounds[1][1]],
        [bounds[1][0], bounds[1][1]],
        [bounds[0][0], bounds[1][1]],
        [bounds[0][0], bounds[0][1]]
    ];

    const startDate = $('#start-date').val();
    const endDate = $('#end-date').val();

    $('#loading-spinner-input').show();
    $('#input_image').hide();
    $('#error-message').hide();

    $.ajax({
        url: '/download_image',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            coordinates: coordinates,
            start_date: startDate,
            end_date: endDate
        }),
        success: function(data) {
            $('#input_image').attr('src', data.displaypath).data('filepath', data.filepath);
            $('#loading-spinner-input').hide();
            $('#input_image').show();
            showToast("success", "Downloaded Area!", "Area has been downloaded successfully and will now be analyzed.");
            $("#analyze").click();
        },
        error: function(error) {
            $('#loading-spinner-input').hide();
            $('#error-message').show().delay(5000).fadeOut();
            showToast("error", "Download Area Error", error.responseJSON.message);
        }
    });
});

// Shows a toast notification using SweetAlert2
function showToast(type, title, message) {
    Swal.fire({
        toast: true,
        position: 'top-end',
        icon: type,
        title: title,
        text: message,
        showConfirmButton: false,
        timer: 4500,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
        }
    });
}
