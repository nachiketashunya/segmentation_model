## Dataset
The ISIC 2016 dataset was utilized for training, validation, and testing the segmentation model.

## Preprocessing
Standard image transformations such as resizing, center cropping, and normalization were applied to both images and masks.

## Model Architecture
- **Encoder**: A MobileNet model pre-trained on ImageNet was used as the encoder.
  - **Task 1**: The pre-trained weights were utilized without fine-tuning.
  - **Task 2**: The pre-trained weights were utilized with fine-tuning.
- **Decoder**: A custom decoder network was designed consisting of several upsampling layers followed by convolutional layers and activation functions.

## Training Procedure
- The model was trained using the Adam optimizer with a binary cross-entropy loss function.
- Training was conducted for 30 epochs with a batch size of 16.
- Evaluation metrics such as Intersection over Union (IoU) and Dice Score were computed during training and validation.
- The training progress was visualized through loss curves and segmented mask comparisons between predictions and ground truth.
