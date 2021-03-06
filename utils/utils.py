import os
import yaml
from shutil import rmtree, copyfile
import logging
import numpy as np
import cv2 as cv
import torch
from tensorboardX import SummaryWriter

from models.CustomNet import CustomNet
from models.resnet import ResNet18, ResNet34, ResNet50, ResNet101, ResNet152

import warnings
warnings.filterwarnings("ignore")


def get_logger():
    logger = logging.getLogger("ClassNets")
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s]-[%(filename)s]: %(message)s ")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def get_tb_writer(tb_logdir, ckpt_dir):
    """
    Args:
        tb_logdir: str, Path to directory fot tensorboard events
        ckpt_dir: str, Path to checkpoints directory
    Return:
        writer: TensorBoard writer
    """
    if '/' in ckpt_dir:
        tb_logdir = os.path.join(tb_logdir, ckpt_dir.split("/")[-1])
    else:
        tb_logdir = os.path.join(tb_logdir, ckpt_dir.split("\\")[-1])
    if os.path.isdir(tb_logdir):
        rmtree(tb_logdir)
    os.mkdir(tb_logdir)
    writer = SummaryWriter(log_dir=tb_logdir)
    return writer


def get_device(device):
    """
    Args:
        device: str, GPU device id
    Return: torch device
    """

    if device == "cpu":
        return torch.device("cpu")
    else:
        assert torch.cuda.is_available(), f"CUDA unavailable, invalid device {device} requested"
        c = 1024 ** 2
        x = torch.cuda.get_device_properties(0)
        print("Using GPU")
        print(f"device{device} _CudaDeviceProperties(name='{x.name}'"
              f", total_memory={x.total_memory / c}MB)")
        return torch.device("cuda:0")


def get_model(arch, num_classes, input_shape, channels=3):
    """
    Args:
        arch: string, Network architecture
        num_classes: int, Number of classes
        input_shape: list/tuple, Input shape of the network
        channels: int, Number of input channels
    Returns:
        model, nn.Module, generated model
    """
    if arch == "CustomNet":
        model = CustomNet(num_classes, channels)
    elif arch.lower() == "resnet18":
        model = ResNet18(num_classes, input_shape, channels)
    elif arch.lower() == "resnet34":
        model = ResNet34(num_classes, input_shape, channels)
    elif arch.lower() == "resnet50":
        model = ResNet50(num_classes, input_shape, channels)
    elif arch.lower() == "resnet101":
        model = ResNet101(num_classes, input_shape, channels)
    elif arch.lower() == "resnet152":
        model = ResNet152(num_classes, input_shape, channels)
    else:
        raise NotImplementedError(f"{arch} not implemented."
                                  f"For supported architectures see documentation")
    return model


def save_model(model, epoch, ckpt_dir, results, logger):
    """ Save model
    Args:
        model: Model for saving
        epoch: Number of epoch
        ckpt_dir: Store directory
        logger:
    """
    best_acc = 0
    best_epoch = 0
    ckpt_dir = os.path.join(ckpt_dir, "checkpoints")
    if not os.path.isdir(ckpt_dir):
        os.makedirs(ckpt_dir)
    ckpt_path = os.path.join(ckpt_dir, "model_epoch" + str(epoch) + ".pt")
    torch.save(model.state_dict(), ckpt_path)
    logger.info(f"Model saved: {ckpt_path}")

    best_ckpt_path = os.path.join(ckpt_dir, "best_model_epoch" + str(epoch) + ".pt")
    for res in results:
        if res["val_accuracy"] > best_acc:
            best_epoch = res["epoch"]
    best_epoch = os.path.join(ckpt_dir, "model_epoch" + str(best_epoch) + ".pt")
    if os.path.isfile(best_epoch):
        copyfile(best_epoch, best_ckpt_path)
    else:
        logger.info(f"The best epoch not found: {best_epoch}")


def load_model(model_path, arch, num_classes, input_shape, channels=3):
    """
    Args:
        model_path: str, Path to model
        arch: str, Network architectire (See documentation for supported architectures)
        num_classes: int, Number of classes
        input_shape: list/tuple, Input shape of the network
        channels: int, Number of input channels
    """

    model = get_model(arch, num_classes, input_shape, channels)

    model.load_state_dict(torch.load(model_path))
    model.eval()

    return model


def get_optimizer(opt, model, lr):
    """
    Args
        opt: string, optimizer from config file
        model: nn.Module, generated model
        lr: float, specified learning rate
    Returns:
        optimizer
    """

    if opt.lower() == "adam":
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    elif opt.lower() == "sgd":
        optimizer = torch.optim.SGD(model.parameters(), lr=lr)
    else:
        raise NotImplementedError(f"Not supported optimizer name: {opt}."
                                  f"For supported optimizers see documentation")
    return optimizer


def preprocess_img(img):
    """ Transform input image to excepted format for network
    Args:
        img: numpy array, Input image
    Return
        img: numpy array, Preprocessed image
    """
    img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    img = cv.resize(img, (240, 160))
    img = np.transpose(img, (2, 0, 1))
    img = img[np.newaxis, ...]
    img = img / 255.
    img = torch.FloatTensor(img)
    return img


def copy_config(config):
    """ Copy used config for training to checkpoints directory
    Args:
    config: Config file
    """
    ckpt_dir = config["Logging"]["ckpt_dir"]
    if not os.path.isdir(ckpt_dir):
        os.makedirs(ckpt_dir)
    out_config_path = os.path.join(ckpt_dir, "config.yaml")
    with open(out_config_path, 'w') as outfile:
        yaml.dump(config, outfile)
