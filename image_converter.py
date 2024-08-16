from logger_config import LoggerConfig
import rasterio
from rasterio.plot import reshape_as_image
from PIL import Image
import numpy as np
import os

class TifImageConverter:
    def __init__(self, output_directory, output_format='png'):
        """
        Initializes the TifImageConverter class.

        Args:
            output_directory (str): The directory where converted files will be saved.
            output_format (str): The format to which the TIFF files will be converted. Default is 'png'.
        """
        self.logger = LoggerConfig.get_logger(self.__class__.__name__)
        self.output_directory = output_directory
        self.output_format = output_format

        # Ensure output directory exists
        if not os.path.exists(self.output_directory):
            os.makedirs(self.output_directory)
            self.logger.info(f"Created output directory at {self.output_directory}")
        else:
            self.logger.info(f"Using existing output directory at {self.output_directory}")

    def convert(self, input_file):
        """
        Convert the GeoTIFF file to the specified format, adjusting bit depth as needed.
        The output file will have the same base name as the input file but with the new extension.

        Args:
            input_file (str): The path to the input GeoTIFF file.

        Returns:
            str: The path to the converted file.
        """
        self.logger.info(f"Converting {input_file} to {self.output_format} format.")
        base_filename = os.path.basename(input_file)
        output_filename = os.path.splitext(base_filename)[0] + f'.{self.output_format}'
        output_file = os.path.join(self.output_directory, output_filename)

        image_data = self.convert_to_uint8(input_file=input_file, png_conversion=True)

        # Convert to a PIL image and save as the specified format
        im = Image.fromarray(image_data)
        
        # Resize image if its width exceeds the maximum allowed width
        max_width = 2500
        if im.width > max_width:
            ratio = max_width / float(im.width)
            new_height = int((float(im.height) * float(ratio)))
            im = im.resize((max_width, new_height), Image.LANCZOS)
            self.logger.info(f"Resized image to width {max_width} pixels while maintaining aspect ratio.")

        im.save(output_file)
        self.logger.info(f"GeoTIFF {input_file} successfully converted to {output_file}.")
        return output_file
    
    def convert_to_uint8(self, input_file, png_conversion=False):
        """
        Convert the GeoTIFF file to 8-bit format, adjusting bit depth if necessary.

        Args:
            input_file (str): The path to the input GeoTIFF file.
            png_conversion (bool): Whether to prepare the data for PNG conversion (3-band color). Default is False.

        Returns:
            np.ndarray or str: The 8-bit image data as a NumPy array (if png_conversion is True) or the input file path.
        """
        self.logger.info(f"Converting {input_file} to 8-bit format.")
        with rasterio.open(input_file) as src:
            image_data = src.read()

            bit_depth = src.dtypes[0]  # Assume all bands have the same dtype
            self.logger.info(f"Image bit depth: {bit_depth}")

            if image_data.shape[0] > 3:
                # Use the first three bands if more than three are present
                image_data = image_data[:3, :, :]

            if png_conversion:
                image_data = reshape_as_image(image_data)

            # Handle different bit depths
            if 'uint8' in bit_depth:
                self.logger.info("Image is already in 8-bit format, no scaling needed.")
                pass
            elif 'uint16' in bit_depth:
                self.logger.info("Scaling 16-bit image data to 8-bit.")
                image_data = np.clip(image_data / 256, 0, 255).astype(np.uint8)
            elif 'float32' in bit_depth or 'float64' in bit_depth:
                self.logger.info("Normalizing floating-point image data to 8-bit.")
                min_val = image_data.min()
                max_val = image_data.max()
                image_data = np.clip((image_data - min_val) / (max_val - min_val) * 255, 0, 255).astype(np.uint8)
            else:
                self.logger.error(f"Unsupported bit depth: {bit_depth}")
                raise ValueError(f"Unsupported bit depth: {bit_depth}")

            if image_data.shape[2] == 1:
                image_data = np.squeeze(image_data, axis=2)
                
            if png_conversion:
                self.logger.info("Returning image data for PNG conversion.")
                return image_data
            else:
                if not 'uint8' in bit_depth:
                    profile = src.profile
                    profile.update(
                        dtype=rasterio.uint8,
                        count=image_data.shape[0]
                    )

                    # Overwrite the input file with the new data
                    self.logger.info(f"Overwriting {input_file} with converted 8-bit data.")
                    with rasterio.open(input_file, 'w', **profile) as dst:
                        dst.write(image_data)
                    
                return input_file
