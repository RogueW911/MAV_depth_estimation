import os
import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import config, utils, model, dataset
import time
from torch.quantization import quantize_dynamic

def train():
    # Set up logging & device
    logging_on = config.config["logging_on"]
    if logging_on:
        os.makedirs(config.config["save_log_path"], exist_ok=True)
        logger = utils.init_logger()
        os.makedirs(config.config["save_event_path"], exist_ok=True)
        writer = SummaryWriter(config.config["save_event_path"])
    device = config.config["device"]
    
    # Load dataset
    train_loader, val_loader = dataset.load_train_val_dataset()
    
    # Load model
    depth_model = model.ShallowDepthModel()
    depth_model.to(device)
    if args.checkpoint:
        depth_model.load_state_dict(torch.load(args.checkpoint))
    print(f"Number of parameters: {depth_model.compute_parameters()}")
    
    # Loss function & optimizer
    loss = nn.MSELoss()
    
    optimizer = torch.optim.Adam(
        depth_model.parameters(), 
        lr=config.config["learning_rate"], 
        weight_decay=config.config["weight_decay"]
        )
    
    best_loss = float("inf")
    counter = 0
    for epoch in range(config.config["epochs"]):
        # Training loop
        for i, (img, depth_vec) in tqdm(enumerate(train_loader)):
            img, depth_vec = img.to(device), depth_vec.to(device)
            
            optimizer.zero_grad()
            pred_depth = depth_model(img) 
            loss_train = loss(pred_depth, depth_vec)
            # print(f"pred_depth: {pred_depth.shape}, depth_vector: {depth_vector.shape}")
            loss_train.backward()
            optimizer.step()
            
            if i % 10 == 0 and logging_on:
                logger.info(f"Epoch {epoch}, Iteration {i}, Loss: {loss_train.item()}")
                writer.add_scalar("Loss/train", loss_train.item(), epoch * len(train_loader) + i)
        
        torch.save(depth_model.state_dict(), os.path.join(config.config["save_model_path"], f"model_{epoch}.pth"))
        
        # Validation loop
        depth_model.eval()
        for i, (img, depth_vec) in enumerate(val_loader):
            img, depth_vec = img.to(device), depth_vec.to(device)
            
            pred_depth = depth_model(img)
            loss_val = loss(pred_depth, depth_vec)
            
            if i % 10 == 0 & logging_on:
                logger.info(f"Epoch {epoch}, Iteration {i}, Val Loss: {loss_val.item()}")
                writer.add_scalar("Loss/val", loss_val.item(), epoch * len(val_loader) + i)
            
            # Early stopping
            # if loss_val < best_loss:
            #     best_loss = loss_val
            #     counter = 0
            # else:
            #     counter += 1
            #     if counter > config.config["patience"]:
            #         if logging_on: logger.info(f"Early stopping at epoch {epoch}.")
            #         break
    if logging_on:
        logger.info("Training complete.")
        writer.close()


def eval(num_imgs, model_id=0):
    '''
    Pick some random input images and run depth estimation on it
    '''
    # Load model
    model_path = config.config["save_model_path"] + f"/model_{model_id}.pth"

    depth_model = model.ShallowDepthModel()
    depth_model.load_state_dict(torch.load(model_path))
    depth_model.eval()
    # depth_model = quantize_dynamic(depth_model, dtype=torch.qint8)
 
    # print(f"Number of parameters: {depth_model.compute_parameters()}")

    # Load images
    eval_loader = dataset.load_eval_dataset(num_imgs)

    # Run depth estimation
    with torch.no_grad():
        for i, (img, _) in enumerate(eval_loader):
            # Run model
            start_time = time.time()
            depth_pred = depth_model(img)
            # print(f"Depth prediction: {depth_pred}")
            max_depth, max_indices = torch.max(depth_pred, dim=1)
            
            print(f"Inference time: {time.time() - start_time:.2f} seconds")
            print(f"Predicted depth & index: {max_depth[0]}, {max_indices[0]}") #  / config.config['output_channels']

    
if __name__ == "__main__":
    args = utils.parse_args()
    if args.mode == "data":
        utils.convert_h5_to_array(args.path)
    elif args.mode == "train":
        train()
    elif args.mode == "eval":
        eval(num_imgs=10, model_id=args.model_id)
    else:
        utils.load_comparison()
        # raise ValueError("Invalid mode. Please choose 'train' or 'eval'.")
