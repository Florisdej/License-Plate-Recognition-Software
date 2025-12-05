#!/usr/bin/env python3
"""
Headless version of License Plate Recognition
For running on Raspberry Pi without GUI (better performance)
Outputs to terminal and saves annotated images/videos
"""
import cv2
import argparse
import sys
import os
from pathlib import Path
from Detect import LicensePlateDetector
from Tracker import Tracker

class HeadlessLicensePlateApp:
    def __init__(self, output_dir="output", confidence_threshold=0.4):
        self.detector = LicensePlateDetector(confidence_threshold=confidence_threshold)
        self.tracker = Tracker(iou_threshold=0.3, timeout_seconds=2.0)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"Confidence threshold: {confidence_threshold}")
        print("-" * 50)

    def process_image(self, image_path):
        """Process a single image"""
        print(f"\nProcessing image: {image_path}")
        
        if not os.path.exists(image_path):
            print(f"Error: Image not found at {image_path}")
            return
        
        # Detect
        result_img, detections = self.detector.detect(image_path)
        
        # Track
        self.tracker.reset()
        active_objects, new_objects = self.tracker.update(detections)
        
        # Report
        if new_objects:
            print(f"Found {len(new_objects)} license plate(s):")
            for obj in new_objects:
                bbox = obj['bbox']
                print(f"  - Plate {obj['id']}: {obj['confidence']:.1%} confidence")
                print(f"    Location: ({bbox[0]}, {bbox[1]}) to ({bbox[2]}, {bbox[3]})")
        else:
            print("No license plates detected")
        
        # Save result
        output_path = self.output_dir / f"result_{Path(image_path).name}"
        cv2.imwrite(str(output_path), result_img)
        print(f"Saved annotated image to: {output_path}")
        
        return new_objects

    def process_video(self, video_path, display=False, save=True):
        """Process a video file"""
        print(f"\nProcessing video: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video at {video_path}")
            return
        
        # Video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Video: {width}x{height} @ {fps} FPS, {total_frames} frames")
        
        # Setup video writer if saving
        out = None
        if save:
            output_path = self.output_dir / f"result_{Path(video_path).name}"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            print(f"Saving to: {output_path}")
        
        frame_count = 0
        detections_log = []
        
        print("\nProcessing frames...")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Process frame
            result_img, detections = self.detector.detect(frame)
            active_objects, new_objects = self.tracker.update(detections)
            
            # Log new detections
            if new_objects:
                for obj in new_objects:
                    print(f"Frame {frame_count}: Detected Plate {obj['id']} ({obj['confidence']:.1%})")
                    detections_log.append({
                        'frame': frame_count,
                        'time': frame_count / fps,
                        'id': obj['id'],
                        'confidence': obj['confidence'],
                        'bbox': obj['bbox']
                    })
            
            # Save/display
            if out:
                out.write(result_img)
            
            if display:
                cv2.imshow('License Plate Detection', result_img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\nStopped by user")
                    break
            
            # Progress
            if frame_count % 30 == 0:
                progress = (frame_count / total_frames) * 100
                print(f"Progress: {frame_count}/{total_frames} ({progress:.1f}%)")
        
        # Cleanup
        cap.release()
        if out:
            out.release()
        if display:
            cv2.destroyAllWindows()
        
        # Summary
        print(f"\n" + "=" * 50)
        print(f"Processing complete!")
        print(f"Frames processed: {frame_count}")
        print(f"Unique plates detected: {len(set(d['id'] for d in detections_log))}")
        print(f"Total detections: {len(detections_log)}")
        
        return detections_log

    def process_camera(self, camera_index=0, display=True, save=False):
        """Process live camera feed"""
        print(f"\nStarting camera {camera_index}...")
        
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f"Error: Could not open camera {camera_index}")
            return
        
        # Setup video writer if saving
        out = None
        if save:
            output_path = self.output_dir / "camera_recording.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            out = cv2.VideoWriter(str(output_path), fourcc, 20.0, (width, height))
            print(f"Recording to: {output_path}")
        
        print("Press 'q' to quit, 's' to save screenshot")
        print("-" * 50)
        
        frame_count = 0
        screenshot_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to read from camera")
                break
            
            frame_count += 1
            
            # Process frame
            result_img, detections = self.detector.detect(frame)
            active_objects, new_objects = self.tracker.update(detections)
            
            # Report new detections
            if new_objects:
                for obj in new_objects:
                    print(f"Detected Plate {obj['id']} ({obj['confidence']:.1%})")
            
            # Add FPS counter to display
            if frame_count % 30 == 0:
                print(f"Frames processed: {frame_count}")
            
            # Save/display
            if out:
                out.write(result_img)
            
            if display:
                cv2.imshow('License Plate Detection (Press Q to quit)', result_img)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\nStopping camera...")
                break
            elif key == ord('s'):
                screenshot_count += 1
                screenshot_path = self.output_dir / f"screenshot_{screenshot_count}.jpg"
                cv2.imwrite(str(screenshot_path), result_img)
                print(f"Screenshot saved: {screenshot_path}")
        
        # Cleanup
        cap.release()
        if out:
            out.release()
        if display:
            cv2.destroyAllWindows()
        
        print(f"\nCamera session ended. Processed {frame_count} frames.")


def main():
    parser = argparse.ArgumentParser(
        description="License Plate Recognition - Headless Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process an image
  python3 app_headless.py --image /path/to/image.jpg
  
  # Process a video
  python3 app_headless.py --video /path/to/video.mp4
  
  # Start camera (with display)
  python3 app_headless.py --camera --display
  
  # Start camera (no display, just logging)
  python3 app_headless.py --camera
        """
    )
    
    # Input source (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--image', type=str, help='Path to image file')
    source_group.add_argument('--video', type=str, help='Path to video file')
    source_group.add_argument('--camera', action='store_true', help='Use camera feed')
    
    # Options
    parser.add_argument('--camera-index', type=int, default=0, help='Camera index (default: 0)')
    parser.add_argument('--output-dir', type=str, default='output', help='Output directory (default: output)')
    parser.add_argument('--confidence', type=float, default=0.4, help='Confidence threshold (default: 0.4)')
    parser.add_argument('--display', action='store_true', help='Display video/camera output')
    parser.add_argument('--no-save', action='store_true', help='Don\'t save output files')
    
    args = parser.parse_args()
    
    # Create app
    app = HeadlessLicensePlateApp(
        output_dir=args.output_dir,
        confidence_threshold=args.confidence
    )
    
    # Process based on input type
    try:
        if args.image:
            app.process_image(args.image)
        elif args.video:
            app.process_video(args.video, display=args.display, save=not args.no_save)
        elif args.camera:
            app.process_camera(
                camera_index=args.camera_index,
                display=args.display,
                save=not args.no_save
            )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
