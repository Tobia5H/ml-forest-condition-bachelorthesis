import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from deepforest import main
import threading

class TreeDetectionApp:
    def __init__(self, root):
        """
        Initialize the TreeDetectionApp class.

        Args:
            root (tk.Tk): The root window of the Tkinter application.
        """
        self.root = root
        self.root.title("Tree Detection App - DeepForest")
        self.root.geometry("900x600")
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(2, weight=10)
        self.root.grid_rowconfigure(3, weight=1)

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.select_button = tk.Button(root, text="Select Image", command=self.select_image)
        self.select_button.grid(row=0, column=0, padx=10, pady=10)

        self.evaluate_button = tk.Button(root, text="Evaluate Picture", command=self.start_evaluation)
        self.evaluate_button.grid(row=0, column=1, padx=10, pady=10)

        self.original_label = tk.Label(root, text="Original Image")
        self.original_label.grid(row=1, column=0, padx=10, pady=10)

        self.evaluated_label = tk.Label(root, text="Evaluated Image")
        self.evaluated_label.grid(row=1, column=1, padx=10, pady=10)

        self.original_image_label = tk.Label(root)
        self.original_image_label.grid(row=2, column=0, padx=10, pady=10)

        self.evaluated_image_label = tk.Label(root)
        self.evaluated_image_label.grid(row=2, column=1, padx=10, pady=10)

        self.progress = ttk.Progressbar(root, orient='horizontal', mode='indeterminate')
        self.progress.grid(row=3, column=1, padx=10, pady=10, sticky='ew')
        self.progress.grid_remove()

        self.image_path = None
        self.model = main.deepforest() 
        self.model.use_release()  # Use the pre-trained DeepForest model

    def select_image(self):
        """
        Open a file dialog to select an image and display it in the original image label.
        """
        self.image_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.tif *.tiff")])
        if self.image_path:
            self.display_image(self.image_path, self.original_image_label, is_evaluated=False)

    def resize_image(self, image, target_size):
        """
        Resize the given image while maintaining the aspect ratio.

        Args:
            image (PIL.Image.Image): The image to be resized.
            target_size (int): The target size for the larger dimension (width or height).

        Returns:
            PIL.Image.Image: The resized image.
        """
        width, height = image.size
        if width < height:
            new_width = target_size
            new_height = int(target_size * (height / width))
        else:
            new_height = target_size
            new_width = int(target_size * (width / height))
        return image.resize((new_width, new_height), Image.ANTIALIAS)

    def start_evaluation(self):
        """
        Start the evaluation process in a separate thread and show a progress bar.
        """
        if not self.image_path:
            messagebox.showwarning("No Image Selected", "Please select an image before evaluating.")
            return

        self.progress.grid()  # Show progress bar
        self.progress.start()
        self.evaluate_button.config(state=tk.DISABLED)

        eval_thread = threading.Thread(target=self.evaluate_image)
        eval_thread.start()

    def evaluate_image(self):
        """
        Evaluate the selected image using the DeepForest model and display the result.
        """
        try:
            # Use DeepForest to evaluate the image
            evaluated_image_path = self.detect_trees(self.image_path)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during evaluation: {str(e)}")
        finally:
            self.progress.stop()
            self.progress.grid_remove()  # Remove progress bar
            self.display_image(evaluated_image_path, self.evaluated_image_label, is_evaluated=True)
            messagebox.showinfo("Success", "The image has been successfully evaluated.")
            self.evaluate_button.config(state=tk.NORMAL)

    def display_image(self, image_path, label, is_evaluated):
        """
        Display the given image in the specified label.

        Args:
            image_path (str): The path to the image to be displayed.
            label (tk.Label): The label in which the image will be displayed.
            is_evaluated (bool): Whether the image is an evaluated image or not.
        """
        image = Image.open(image_path)
        image = image.resize((400, 400))  # Resize image to fit the label
        image = ImageTk.PhotoImage(image)
        label.config(image=image)
        label.image = image

    def detect_trees(self, image_path):
        """
        Detect trees in the given image using the DeepForest model and save the evaluated image.

        Args:
            image_path (str): The path to the image to be evaluated.

        Returns:
            str: The path to the evaluated image.
        """
        # Detect trees using DeepForest
        img = self.model.predict_image(path=image_path, return_plot=True)
        
        # Create and save the plot of the evaluated image
        img = img[:, :, ::-1]  # Convert BGR to RGB
        fig, ax = plt.subplots()
        ax.imshow(img)
        
        # Increase thickness and change color of bounding boxes
        detections = self.model.predict_image(path=image_path)
        for index, row in detections.iterrows():
            rect = plt.Rectangle((row['xmin'], row['ymin']), row['xmax'] - row['xmin'], row['ymax'] - row['ymin'], fill=False, color='red', linewidth=2)
            ax.add_patch(rect)
        
        ax.axis('off')
        
        evaluated_image_path = "evaluated_image.png"
        plt.savefig(evaluated_image_path, bbox_inches='tight', pad_inches=0)
        plt.close()

        return evaluated_image_path

if __name__ == "__main__":
    root = tk.Tk()
    app = TreeDetectionApp(root)
    root.mainloop()
