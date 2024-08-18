# FALS Web App Documentation

## Overview

The FALS (Forest Analysis and Location System) web application is designed to detect trees in high-resolution satellite images, calculate the Normalized Difference Vegetation Index (NDVI) for the detected tree areas, and provide statistical analysis of these NDVI values. The application supports uploading custom images or selecting areas on an interactive map to perform the analysis.

## Features

- **Tree Detection**: Automatically detect trees in uploaded or selected satellite images using the [Detectree2](https://github.com/PatBall1/detectree2) model.
- **NDVI Calculation**: Compute NDVI for the areas where trees have been detected.
- **Statistical Analysis**: Provide mean, median, minimum, maximum, and standard deviation of NDVI values.
- **Interactive Map Selection**: Choose an area of interest on a map to download satellite imagery directly from the Google Earth Sentinel-2 Harmonized Collection (Currently limited to EPSG:25833 - ETRS89 / UTM zone 33N).
- **Settings Customization**: Configure tile size, buffer size, and crown confidence to tailor the analysis according to your needs.
- **Azure VM Configuration**: The application is configured to run on an Azure Virtual Machine, ensuring scalability and performance.

## Tree Detection Model

The application uses the **[Detectree2](https://github.com/PatBall1/detectree2)** model for tree detection. Currently, it leverages a pretrained model specifically designed for mapping trees in urban environments, particularly trained on data from Cambridge, UK. This model is optimized for detecting trees in urban settings and is integrated into the FALS Web App to provide reliable and accurate results.

## Project Background

This repository contains the programming project for the Bachelor's thesis titled "Assessment of Forest Conditions Using Satellite Images and Machine Learning" (German: *"Zustandsbewertung von Wäldern mittels Satellitenbildern und Machine Learning"*). The project is focused on using advanced machine learning techniques to evaluate the health and status of forests through satellite imagery.

## Getting Started

### Image Upload

1. **Supported Formats**: TIFF or TIF (preferably with a resolution around 30cm).
2. **Upload Process**:
   - Navigate to the "Upload Image" section.
   - Select and upload your image in the supported format.

### Interactive Map Selection

1. **Accessing the Map**:
   - Navigate to the "Interactive Map" section.
   - Use the map interface to zoom in and select the area of interest.
   
2. **Downloading Image**:
   - Ensure that the selected area falls within the EPSG:25833 - ETRS89 / UTM zone 33N coordinate system.
   - Click "Download Image" to retrieve the satellite image of the selected area.

> **Note**: The application currently supports a static EPSG setting. Dynamic CRS implementation for downloaded images is on the TODO list.

### Configuring Settings

- **Tile Width**: Define the width of each tile in meters.
- **Tile Height**: Define the height of each tile in meters.
- **Buffer**: Set the buffer size in meters to be applied around each tile.
- **Crown Confidence**: Adjust the confidence level for detecting tree crowns.

> **Tip**: Use the same format that the model was trained on for optimal results. Adjusting these settings can help balance performance and accuracy based on your system's resources.

### Running the Analysis

1. **Start Analysis**: Once the image is uploaded or selected, and settings are configured, click "Run Analysis."
2. **Results**:
   - **Tree Detection**: The processed image will display detected trees circled in red.
   - **NDVI Image**: Below the tree detection image, a masked NDVI image shows the NDVI values for the detected tree areas.
   - **Statistics Table**: Next to the images, a table displays statistical data, including the mean, median, minimum, maximum, and standard deviation of the NDVI values.

## Future Improvements

### TODO:

- **Dynamic CRS**: Implement support for dynamic coordinate reference systems (CRS) for downloaded images from the interactive map.
- **Health Showcase**: Add a feature to evaluate forest health based on NDVI values. For example, a mean NDVI of 245 (on a scale of 0-255) could indicate a very healthy forest.

### Nice to Have:

- **High-Resolution Downloads**: Enable high-resolution downloads from fee-based providers within the interactive map interface (acknowledging potential cost implications).