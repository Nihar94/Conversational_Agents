import sys, os, argparse
import numpy as np
import cv2
import matplotlib.pyplot as plt

import torch
import torch.nn as nn
from torch.autograd import Variable
from torch.utils.data import DataLoader
from torchvision import transforms
import torch.backends.cudnn as cudnn
import torchvision
import torch.nn.functional as F
from PIL import Image

import datasets, hopenet, utils
import pdb
from skimage import io

sys.path.append('/home/nihar/Desktop/HRIProject/DFace')
from dface.core.detect import create_mtcnn_net, MtcnnDetector
import dface.core.vision as vision
import dlib

def parse_args():
    """Parse input arguments."""
    parser = argparse.ArgumentParser(description='Head pose estimation using the Hopenet network.')
    parser.add_argument('--gpu', dest='gpu_id', help='GPU device id to use [0]',
            default=0, type=int)
    parser.add_argument('--snapshot', dest='snapshot', help='Path of model snapshot.',
          default='../models/hopenet_robust_alpha1.pkl', type=str)
    parser.add_argument('--face_model', dest='face_model', help='Path of DLIB face detection model.',
          default='../mmod_human_face_detector.dat', type=str)
    parser.add_argument('--video', dest='video_path', help='Path of video', default='../video/video2.mp4')
    parser.add_argument('--output_string', dest='output_string', help='String appended to output file')
    parser.add_argument('--n_frames', dest='n_frames', help='Number of frames', type=int, default=5000)
    parser.add_argument('--fps', dest='fps', help='Frames per second of source video', type=float, default=30.)
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = parse_args()

    cudnn.enabled = True

    batch_size = 1
    gpu = args.gpu_id
    snapshot_path = args.snapshot
    out_dir = 'output/video'
    video_path = args.video_path

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if not os.path.exists(args.video_path):
        sys.exit('Video does not exist')

    # ResNet50 structure
    model = hopenet.Hopenet(torchvision.models.resnet.Bottleneck, [3, 4, 6, 3], 66)

    # Dlib face detection model
    # cnn_face_detector = dlib.cnn_face_detection_model_v1(args.face_model)
    
    pnet, rnet, onet = create_mtcnn_net(p_model_path="/home/nihar/Desktop/HRIProject/DFace/model_store/pnet_epoch.pt", r_model_path="/home/nihar/Desktop/HRIProject/DFace/model_store/rnet_epoch.pt", o_model_path="/home/nihar/Desktop/HRIProject/DFace/model_store/onet_epoch.pt", use_cuda=True)
    mtcnn_detector = MtcnnDetector(pnet=pnet, rnet=rnet, onet=onet, min_face_size=24)

    print('Loading snapshot.')
    # Load snapshot
    saved_state_dict = torch.load(snapshot_path)
    model.load_state_dict(saved_state_dict)

    print('Loading data.')

    transformations = transforms.Compose([transforms.Scale(224),
    transforms.CenterCrop(224), transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])

    model.cuda(gpu)

    print('Ready to test network.')

    # Test the Model
    model.eval()  # Change model to 'eval' mode (BN uses moving mean/var).
    total = 0

    idx_tensor = [idx for idx in range(66)]
    idx_tensor = torch.FloatTensor(idx_tensor).cuda(gpu)

    video = cv2.VideoCapture(video_path)
    test_img = cv2.imread('../video/test.jpg')
    # New cv2
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))   # float
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)) # float

    # Define the codec and create VideoWriter object
    # fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    # out = cv2.VideoWriter('output/video/output-%s.avi' % args.output_string, fourcc, args.fps, (width, height))

    # # Old cv2
    # width = int(video.get(cv2.cv.CV_CAP_PROP_FRAME_WIDTH))   # float
    # height = int(video.get(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT)) # float
    #
    # # Define the codec and create VideoWriter object
    # fourcc = cv2.cv.CV_FOURCC(*'MJPG')
    # out = cv2.VideoWriter('output/video/output-%s.avi' % args.output_string, fourcc, 30.0, (width, height))

    txt_out = open('output/video/output-%s.txt' % args.output_string, 'w')

    frame_num = 1
    import matplotlib.pyplot as plt

    while frame_num <= args.n_frames:
        print(frame_num)

        ret,frame = video.read()
        if ret == False:
            break
        # frame1 = test_img
        # frame = cv2.transpose(cv2.resize(frame, (480,640), interpolation = cv2.INTER_CUBIC))
        
        cv2_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        # dets = cnn_face_detector(cv2_frame, 1)
        bboxs, landmarks = mtcnn_detector.detect_face(frame)
        #print(frame.shape)
        
        for idx, det in enumerate(bboxs):
            # Get x_min, y_min, x_max, y_max, conf
            x_min = det[0] #.rect.left()
            y_min = det[1] #.rect.top()
            x_max = det[2] #.rect.right()
            y_max = det[3] #.rect.bottom()
            conf = det[4] #.confidence
            #vision.vis_face(cv2_frame,bboxs,landmarks)
        
            if conf > 0.9:
                bbox_width = abs(x_max - x_min)
                bbox_height = abs(y_max - y_min)
                x_min -= 2 * bbox_width / 4
                x_max += 2 * bbox_width / 4
                y_min -= 3 * bbox_height / 4
                y_max += bbox_height / 4
                x_min = max(x_min, 0); y_min = max(y_min, 0)
                x_max = min(frame.shape[1], x_max); y_max = min(frame.shape[0], y_max)
                # Crop image
                #pdb.set_trace()
                img = cv2_frame[int(y_min):int(y_max),int(x_min):int(x_max)]
                img = Image.fromarray(img)

                # Transform
                img = transformations(img)
                img_shape = img.size()
                img = img.view(1, img_shape[0], img_shape[1], img_shape[2])
                img = Variable(img).cuda(gpu)

                yaw, pitch, roll = model(img)
                #pdb.set_trace()

                yaw_predicted = F.softmax(yaw)
                pitch_predicted = F.softmax(pitch)
                roll_predicted = F.softmax(roll)
                # Get continuous predictions in degrees.
                yaw_predicted = torch.sum(yaw_predicted.data[0] * idx_tensor) * 3 - 99
                pitch_predicted = torch.sum(pitch_predicted.data[0] * idx_tensor) * 3 - 99
                roll_predicted = torch.sum(roll_predicted.data[0] * idx_tensor) * 3 - 99

                # print(new frame with cube and axis
                txt_out.write(str(frame_num) + ' %f %f %f\n' % (yaw_predicted, pitch_predicted, roll_predicted))
                #utils.plot_pose_cube(frame, yaw_predicted, pitch_predicted, roll_predicted, (x_min + x_max) / 2, (y_min + y_max) / 2, size = bbox_width)
                utils.draw_axis(frame, yaw_predicted, pitch_predicted, roll_predicted, tdx = (x_min + x_max) / 2, tdy= (y_min + y_max) / 2, size = bbox_height/2)
                # Plot expanded bounding box
                # cv2.rectangle(frame, (int(x_min), int(y_min)), (int(x_max), int(y_max)), (0,255,0), 1)
                
                cv2.imshow('video',frame)
                k = cv2.waitKey(1) & 0xFF
                if( k ==ord('q')):
                    cv2.destroyWindow('video')
                    video.release()
                    cv2.destroyAllWindows()
                    break
        #out.write(frame)
        frame_num += 1
        
    #out.release()
