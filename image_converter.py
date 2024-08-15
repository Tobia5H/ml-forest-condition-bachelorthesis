import rasterio
from rasterio.plot import reshape_as_image
from PIL import Image
import numpy as np
import os

class TifImageConverter:
    def __init__(self, output_directory, output_format='png'):
        self.output_directory = output_directory
        self.output_format = output_format

        # Ensure output directory exists
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)

    def convert(self, input_file):
        """
        Convert the GeoTIFF file to the specified format, adjusting bit depth as needed.
        The output file will have the same base name as the input file but with the new extension.
        """
        base_filename = os.path.basename(input_file)
        output_filename = os.path.splitext(base_filename)[0] + f'.{self.output_format}'
        output_file = os.path.join(self.output_directory, output_filename)

        image_data = self.convert_to_uint8(input_file=input_file, png_conversion=True)

        # Convert to a PIL image and save as the specified format
        im = Image.fromarray(image_data)
            
        max_width = 2500
        if im.width > max_width:
            ratio = max_width / float(im.width)
            new_height = int((float(im.height) * float(ratio)))
            im = im.resize((max_width, new_height), Image.LANCZOS)
            
        im.save(output_file)

        print(f"GeoTIFF {input_file} has been successfully converted to {output_file}")
        return output_file
    
    def convert_to_uint8(self, input_file, png_conversion = False):
        """
        Convert the GeoTIFF file to the specified bit depth.
        The output file will have the same base name as the input file but with the new extension.
        """

        with rasterio.open(input_file) as src:
            # Read the image data
            image_data = src.read()

            # Get metadata to understand bit depth
            bit_depth = src.dtypes[0]  # Assume all bands have the same dtype

            # Convert the data to a format suitable for saving as PNG
            if image_data.shape[0] > 3:
                # Use the first three bands if more than three are present
                image_data = image_data[:3, :, :]

            if png_conversion:
                # Reshape the image data to (rows, cols, bands)
                image_data = reshape_as_image(image_data)

            # Handle different bit depths
            if 'uint8' in bit_depth:
                # 8-bit data, no scaling needed
                pass
            elif 'uint16' in bit_depth:
                # 16-bit data, scale down to 8-bit (0-255)
                image_data = np.clip(image_data / 256, 0, 255).astype(np.uint8)
            elif 'float32' in bit_depth or 'float64' in bit_depth:
                # 32-bit or 64-bit floating-point data, normalize to 0-255
                min_val = image_data.min()
                max_val = image_data.max()
                image_data = np.clip((image_data - min_val) / (max_val - min_val) * 255, 0, 255).astype(np.uint8)
            else:
                raise ValueError(f"Unsupported bit depth: {bit_depth}")

            if image_data.shape[2] == 1:
                image_data = np.squeeze(image_data, axis=2)
                
            if png_conversion:
                return image_data
            else:
                if not 'uint8' in bit_depth:
                    # Define the metadata for the output file
                    profile = src.profile
                    profile.update(
                        dtype=rasterio.uint8,
                        count=image_data.shape[0]
                    )

                    # Overwrite the input file with the new data
                    with rasterio.open(input_file, 'w', **profile) as dst:
                        dst.write(image_data)
                    
                return input_file