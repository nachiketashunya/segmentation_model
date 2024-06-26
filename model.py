# -*- coding: utf-8 -*-
"""
Colab Linl: https://colab.research.google.com/drive/1UaIxzNzYkroossxgrh7co0GTfingVJv4

## Importing necessary libraries
"""

from google.colab import drive
drive.mount('/content/drive')

from sklearn import datasets
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import recall_score, precision_score, accuracy_score, precision_recall_curve
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns
import os
import cv2
from PIL import Image
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torchvision
import torchvision.transforms as transforms
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
import torchvision.models as models
from torch.utils.data import random_split
from torchsummary import summary

dataset_path = "/content/drive/MyDrive/Assignment 3/ISIC 2016"
# dataset_path = "/content/drive/MyDrive/M.Tech. Sem 2/Deep Learning/Assignment 3/ISIC 2016"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

train_image_dir = dataset_path + "/train"
train_mask_dir = dataset_path + "/train_masks"
test_image_dir = dataset_path + "/test"
test_mask_dir = dataset_path + "/test_masks"

print(os.listdir(train_mask_dir)[0])
print(os.listdir(train_image_dir)[0])
print(os.path.splitext("ISIC_0000000.png")[0])

def plot_image_with_mask(image, mask):
    fig, axes = plt.subplots(1, 3, figsize=(5, 6))

    # Plot the original image
    axes[0].imshow(image)
    axes[0].set_title('Original Image')
    axes[0].axis('off')

    # Plot the mask
    axes[1].imshow(mask, cmap="gray")
    axes[1].set_title('Mask')
    axes[1].axis('off')

    # Plot the segmented mask
    axes[2].imshow(image)
    axes[2].imshow(mask, alpha=0.5, cmap='viridis')  # Overlay mask on the image
    axes[2].set_title('Segmented Mask')
    axes[2].axis('off')

    plt.tight_layout()
    plt.show()

class ImageMaskVisualization():
  def __init__(self, image_dir, mask_dir):
    self.image_dir = image_dir
    self.mask_dir = mask_dir

  def visualize(self, i):
      image_filename = os.listdir(self.image_dir)[i]
      mask_filename = os.path.splitext(image_filename)[0] + ".png"

      image_path = os.path.join(self.image_dir, image_filename)
      mask_path = os.path.join(self.mask_dir, mask_filename)

      image = cv2.imread(image_path)
      mask = cv2.imread(mask_path)

      plot_image_with_mask(image, mask)

train_visualize = ImageMaskVisualization(train_image_dir, train_mask_dir)

for i in [10, 45, 300, 413]:
  train_visualize.visualize(i)

class ISICDataset(Dataset):
    def __init__(self, image_dir, mask_dir, transform=None):
        """
        Args:
            image_dir (str): Path to the directory containing images.
            mask_dir (str): Path to the directory containing masks.
            transform (callable, optional): Optional transform to be applied to images and masks.
        """
        self.image_paths = [os.path.join(image_dir, x) for x in os.listdir(image_dir)]
        self.mask_paths = [os.path.join(mask_dir, x) for x in os.listdir(mask_dir)]
        self.transform = transform

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
      image_path = self.image_paths[idx]
      mask_path = self.mask_paths[idx]

      image, mask = Image.open(image_path), Image.open(mask_path)

      # Potential background class handling (if needed):
      # mask = mask - 1

      if self.transform:
        image = self.transform['img_transform'](image)
        mask = self.transform['mask_transform'](mask)  # Apply transformations to mask as well

      # mask = mask.squeeze(0)
      return image, mask

config = {
    'batch_size': 16,
    'num_classes': 1
}

image_transform = transforms.Compose([
    transforms.Resize(128),
    transforms.CenterCrop(128),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

mask_transform = transforms.Compose([
    transforms.Resize(128),
    transforms.CenterCrop(128),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor()
])

transform = {
    "img_transform": image_transform,
    "mask_transform": mask_transform
}

isic_train_dataset = ISICDataset(image_dir=train_image_dir, mask_dir=train_mask_dir, transform=transform)

# Split the dataset into training and validation sets
val_size = 0.1
train_size = 1 - val_size
train_dataset, val_dataset = random_split(isic_train_dataset, lengths=[train_size, val_size])

# Create DataLoaders for both training and validation sets
isic_train_loader = DataLoader(train_dataset, batch_size=config['batch_size'], shuffle=True)
isic_val_loader = DataLoader(val_dataset, batch_size=config['batch_size'], shuffle=False)  # Shuffle is usually not desired for validation


isic_test_dataset = ISICDataset(image_dir=test_image_dir, mask_dir=test_mask_dir, transform=transform)
isic_test_loader = DataLoader(isic_test_dataset, batch_size=config['batch_size'], shuffle=True)

# print(torch.unique(x[1][0][0]))

def plot_mask(mask, label):
    fig, axes = plt.subplots(1, 2, figsize=(5, 6))

    # Plot the original image
    axes[0].imshow(label)
    axes[0].set_title('Label Mask')
    axes[0].axis('off')

    # Plot the segmented mask
    axes[1].imshow(mask)
    axes[1].set_title('Predicted Mask')
    axes[1].axis('off')

    plt.tight_layout()
    plt.show()

class MobileNetDecoder(nn.Module):
    def __init__(self, in_channels, num_classes):
        super(MobileNetDecoder, self).__init__()

        self.up1 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.conv1 = nn.Conv2d(in_channels, 64, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu1 = nn.LeakyReLU(inplace=True)

        self.up2 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.conv2 = nn.Conv2d(64, 32, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        self.relu2 = nn.LeakyReLU(inplace=True)

        self.up3 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.conv3 = nn.Conv2d(32, 16, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(16)
        self.relu3 = nn.LeakyReLU(inplace=True)

        self.up4 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.conv4 = nn.Conv2d(16, 8, kernel_size=3, padding=1)
        self.bn4 = nn.BatchNorm2d(8)
        self.relu4 = nn.LeakyReLU(inplace=True)

        self.up5 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.conv5 = nn.Conv2d(8, 1, kernel_size=3, padding=1)
        self.sigmoid = nn.Sigmoid()
        self.dropout = nn.Dropout(p=0.5)

    def forward(self, x):
        x = self.up1(x)
        x = self.relu1(self.bn1(self.conv1(x)))

        x = self.up2(x)
        x = self.relu2(self.bn2(self.conv2(x)))

        x = self.up3(x)
        x = self.relu3(self.bn3(self.conv3(x)))

        x = self.up4(x)
        x = self.relu4(self.bn4(self.conv4(x)))

        x = self.up5(x)
        x = self.sigmoid(self.conv5(x))
        return x

class EncoderDecoder(nn.Module):
    def __init__(self, mobilenet, decoder):
        super(EncoderDecoder, self).__init__()
        self.mobilenet = mobilenet
        self.decoder = decoder

    def forward(self, x):
        x = self.mobilenet.features(x)
        x = self.decoder(x)
        return x

class MobileNetTrainer():
    def __init__(self, model, train_loader, num_classes, val_loader=[], test_loader=[], lr=0.001):
        self.model = model
        self.train_loader = train_loader
        self.test_loader = test_loader
        self.val_loader = val_loader
        self.lr = lr
        self.criterion = nn.BCELoss()
        self.optimizer = optim.Adam(model.parameters(), lr=self.lr)
        self.training_losses = []
        self.num_classes = num_classes
        self.val_losses = []
        self.l2_penalty = 1e-5

    def train(self, epochs):
        print(f"Training with {epochs} epochs\n")
        for epoch in range(epochs):
            vis = True
            self.model.train()  # Training Mode of torch model
            total_loss = 0.0
            iou_scores = []
            dice_scores = []

            self.model = self.model.to(device)

            for inputs, labels in self.train_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                self.optimizer.zero_grad()
                outputs = self.model(inputs)  # Forward pass

                loss = self.criterion(outputs, labels)

                loss.backward()  # Backward pass
                self.optimizer.step()  # Update the weights

                total_loss += loss.item()

                ious, dices = self.calculate_dice_iou(outputs, labels)

                iou_scores.extend(ious)
                dice_scores.extend(dices)

            # Average training loss and accuracy for this epoch
            avg_loss = total_loss / len(self.train_loader)
            # Save training loss for plotting
            self.training_losses.append(avg_loss)

            val_results = self.validate()
            self.val_losses.append(val_results['val_loss'])

            avg_iou = sum(iou_scores) / len(iou_scores)
            avg_dice = sum(dice_scores) / len(dice_scores)

            self.print_training_metrics(epoch, epochs, avg_loss, val_results['val_loss'], avg_iou, val_results['val_iou'], avg_dice, val_results['val_dice'])
            self.on_epoch_plot_mask("Training", outputs, labels)
            self.on_epoch_plot_mask("Validation", val_results['outputs'], val_results['labels'])

    def on_epoch_plot_mask(self, dataset, outputs, labels):
        output_np = outputs[0].detach().cpu().numpy().transpose(1, 2, 0)
        label_np = labels[0].detach().cpu().numpy().transpose(1, 2, 0)

        plt.figure(figsize=(7, 3))
        combined_image = np.concatenate([output_np, label_np], axis=1)

        plt.imshow(combined_image, vmin=0, vmax=1, cmap="gray")
        plt.title(f"{dataset} - Prediction (Left) vs. Label (Right)")
        plt.axis('off')
        plt.show()

    def calculate_dice_iou(self, predictions, ground_truths):
        ious = []
        dices = []

        for prediction, ground_truth in zip(predictions, ground_truths):
          intersection = (prediction * ground_truth).sum()  # Element-wise multiplication
          union = (prediction + ground_truth).sum() - intersection  # Avoid double counting
          iou = intersection / (union + 1e-6)  # Avoid division by zero
          dice_score = (2 * intersection) / (prediction.sum() + ground_truth.sum() + 1e-6)  # Avoid division by zero

          ious.append(iou)
          dices.append(dice_score)

        return ious, dices

    def validate(self):
        self.model.eval()  # Evaluation Mode
        val_loss = 0.0
        correct = 0
        total = 0
        iou_scores, dice_scores = [], []

        with torch.no_grad():
            for inputs, labels in self.val_loader:
                inputs, labels = inputs.to(device), labels.to(device)

                outputs = self.model(inputs)
                loss = self.criterion(outputs, labels)
                val_loss += loss.item()

                ious, dices = self.calculate_dice_iou(outputs, labels)

                iou_scores.extend(ious)
                dice_scores.extend(dices)

        avg_iou = sum(iou_scores) / len(iou_scores)
        avg_dice = sum(dice_scores) / len(dice_scores)
        avg_val_loss = val_loss / len(self.val_loader)

        return {
            'val_iou': avg_iou,
            'val_dice': avg_dice,
            'val_loss': avg_val_loss,
            'outputs': outputs,
            'labels': labels
        }

    def evaluate(self):
        self.model.eval()  # Evaluation Mode
        test_loss = 0.0
        correct = 0
        total = 0
        iou_scores, dice_scores = [], []

        with torch.no_grad():
            for inputs, labels in self.test_loader:
                inputs, labels = inputs.to(device), labels.to(device)

                outputs = self.model(inputs)
                loss = self.criterion(outputs, labels)
                test_loss += loss.item()

                ious, dices = self.calculate_dice_iou(outputs, labels)

                iou_scores.extend(ious)
                dice_scores.extend(dices)

        avg_iou = sum(iou_scores) / len(iou_scores)
        avg_dice = sum(dice_scores) / len(dice_scores)

        avg_test_loss = test_loss / len(self.test_loader)

        return avg_test_loss, avg_iou, avg_dice

    def plot_loss_curves(self):
        epochs = range(1, len(self.training_losses) + 1)

        # Create a new figure
        plt.figure(figsize=(8, 6))

        # Plot Loss Curves
        plt.plot(epochs, self.training_losses, label='Training Loss', color='tab:red')
        plt.plot(epochs, self.val_losses, label='Validation Loss', linestyle='dashed', color='tab:orange')

        # Customize the plot
        plt.xlabel('Epoch', fontsize=12)
        plt.ylabel('Loss', fontsize=12)
        plt.title('Loss vs. Epoch', fontsize=14)
        plt.legend(loc='upper right', fontsize=10)
        plt.grid(True)

        # Show plot
        plt.tight_layout()
        plt.show()

    def print_training_metrics(self, epoch, epochs, avg_loss, val_loss, avg_iou, val_iou, avg_dice, val_dice):
        """Prints training metrics with separator box."""

        box_char = "-"
        sep_length = 60

        # Construct the separator box
        separator = box_char * sep_length

        # Format the training metrics using dedent for cleaner multi-line strings
        metrics_text = f"""
            Epoch {epoch + 1}/{epochs}
            Training/Loss: {avg_loss:.4f}, Validation/Loss: {val_loss:.4f}
            Training/IoU: {avg_iou:.4f}, Validation/IoU: {val_iou: .4f}
            Training/Dice: {avg_dice:.4f}, Validation/Dice: {val_dice: .4f}
        """

        # Print the separator box, metrics, and another separator
        print(separator)
        print(metrics_text)
        print(separator)

config.update({
    'num_epochs': 30,
    'learning_rate': 0.01
})

mobilenet_encoder = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
# Freeze encoder weights (optional)
for param in mobilenet_encoder.parameters():
  param.requires_grad = False

mobilenet_decoder = MobileNetDecoder(in_channels=1280, num_classes=config['num_classes'])

mobilenet_decoder = mobilenet_decoder.to(device)
summary(mobilenet_decoder, input_size=(1280, 4, 4))

trainable_params = sum(p.numel() for p in mobilenet_encoder.parameters() if p.requires_grad)
non_trainable_params = sum(p.numel() for p in mobilenet_encoder.parameters() if not p.requires_grad)

print(f"MobileNet Encoder Model Setup: ")
print(f"----Trainable parameters: {trainable_params}")
print(f"----Non-trainable parameters: {non_trainable_params}")

model = EncoderDecoder(mobilenet_encoder, mobilenet_decoder)

trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
non_trainable_params = sum(p.numel() for p in model.parameters() if not p.requires_grad)

print(f"Combined Model Setup: ")
print(f"----Trainable parameters: {trainable_params}")
print(f"----Non-trainable parameters: {non_trainable_params}")

mnet_trainer = MobileNetTrainer(model, isic_train_loader,  test_loader=isic_test_loader, val_loader=isic_val_loader, num_classes=config['num_classes'])

mnet_trainer.train(config['num_epochs'])

mnet_trainer.plot_loss_curves()

test_loss, test_iou, test_dice = mnet_trainer.evaluate()
print(f"Test Loss: {test_loss: 0.4f}, Test IoU: {test_iou: 0.4f}, Test Dice Score: {test_dice: 0.4f}")

def plot_masks(test_loader, model, num_images=10):
    model.eval()
    with torch.no_grad():
        for i, (images, labels) in enumerate(test_loader):
            if i >= num_images:
                break

            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            predicted_masks = outputs.squeeze(1).cpu().numpy()
            label_masks = labels.squeeze(1).cpu().numpy()

            for j in range(images.size(0)):
                plt.figure(figsize=(5, 5))

                plt.subplot(1, 2, 1)
                plt.imshow(label_masks[j], cmap='gray')
                plt.title('Label Mask')
                plt.axis('off')

                plt.subplot(1, 2, 2)
                plt.imshow(predicted_masks[j], cmap='gray')
                plt.title('Generated Mask')
                plt.axis('off')

                plt.show()
                break

# Usage example:
plot_masks(isic_test_loader, model, num_images=10)

"""# Finetunning"""

mobilenet_encoder_ft = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
mobilenet_decoder_ft = MobileNetDecoder(in_channels=1280, num_classes=config['num_classes'])

model_ft = EncoderDecoder(mobilenet_encoder_ft, mobilenet_decoder_ft)

trainable_params = sum(p.numel() for p in model_ft.parameters() if p.requires_grad)
non_trainable_params = sum(p.numel() for p in model_ft.parameters() if not p.requires_grad)

print(f"FineTunning Combined Model Setup: ")
print(f"----Trainable parameters: {trainable_params}")
print(f"----Non-trainable parameters: {non_trainable_params}")

config['learing_rate'] = 0.0001

mnet_trainer_ft = MobileNetTrainer(model_ft, isic_train_loader,  test_loader=isic_test_loader, val_loader=isic_val_loader, num_classes=config['num_classes'])

mnet_trainer_ft.train(config['num_epochs'])

mnet_trainer_ft.plot_loss_curves()

test_loss, test_iou, test_dice = mnet_trainer_ft.evaluate()
print(f"Test Loss: {test_loss: 0.4f}, Test IoU: {test_iou: 0.4f}, Test Dice Score: {test_dice: 0.4f}")

def plot_masks(test_loader, model, num_images=10):
    model.eval()
    with torch.no_grad():
        for i, (images, labels) in enumerate(test_loader):
            if i >= num_images:
                break

            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            predicted_masks = outputs.squeeze(1).cpu().numpy()
            label_masks = labels.squeeze(1).cpu().numpy()

            for j in range(images.size(0)):
                plt.figure(figsize=(5, 5))

                plt.subplot(1, 2, 1)
                plt.imshow(label_masks[j], cmap='gray')
                plt.title('Label Mask')
                plt.axis('off')

                plt.subplot(1, 2, 2)
                plt.imshow(predicted_masks[j], cmap='gray')
                plt.title('Generated Mask')
                plt.axis('off')

                plt.show()
                break

plot_masks(isic_test_loader, model_ft, num_images=10)

def mask_gen_comparison(test_loader, model_ft, model, num_images=10):
    model.eval()
    with torch.no_grad():
        for i, (images, labels) in enumerate(test_loader):
            if i >= num_images:
                break

            images = images.to(device)
            labels = labels.to(device)

            outputs_ft = model_ft(images)
            outputs = model(images)

            pred_ft = outputs_ft.squeeze(1).cpu().numpy()
            pred = outputs.squeeze(1).cpu().numpy()

            label_masks = labels.squeeze(1).cpu().numpy()

            for j in range(images.size(0)):
                plt.figure(figsize=(7, 6))


                plt.subplot(1, 3, 1)
                plt.imshow(label_masks[j], cmap='gray')
                plt.title('Label Mask')
                plt.axis('off')

                plt.subplot(1, 3, 2)
                plt.imshow(pred_ft[j], cmap='gray')
                plt.title('Task-2 Mask')
                plt.axis('off')

                plt.subplot(1, 3, 3)
                plt.imshow(pred[j], cmap='gray')
                plt.title('Task-1 Mask')
                plt.axis('off')

                plt.show()
                break

mask_gen_comparison(isic_test_loader, model_ft, model, num_images=2)
