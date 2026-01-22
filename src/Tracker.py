import time
import math

class Tracker:
    def __init__(self, iou_threshold=0.3, distance_threshold=100, timeout_seconds=3.0):
        """
        Initialize the tracker with configurable thresholds.
        
        Args:
            iou_threshold: Minimum IoU for matching (0.3 = 30% overlap)
            distance_threshold: Maximum pixel distance between centers for fallback matching
            timeout_seconds: How long to keep a track alive without updates
        """
        self.iou_threshold = iou_threshold
        self.distance_threshold = distance_threshold
        self.timeout_seconds = timeout_seconds
        
        # Store tracked objects: {id: {'bbox', 'label', 'confidence', 'last_seen', 'center'}}
        self.tracked_objects = {}
        self.next_id = 1

    def update(self, detections):
        """
        Update tracked objects with new detections.
        
        Args:
            detections: List of dicts with keys 'bbox', 'label', 'confidence'
            
        Returns:
            active_objects: List of all currently tracked objects
            new_objects: List of objects that were newly detected in this frame
        """
        current_time = time.time()
        new_objects = []
        
        # Create a list of unassigned detection indices
        unassigned_det_indices = list(range(len(detections)))
        
        # Track which objects were updated
        updated_track_ids = set()

        # Match detections to existing tracks using a multi-strategy approach
        for track_id, track_data in list(self.tracked_objects.items()):
            best_match_idx = -1
            best_match_score = 0
            
            for i in unassigned_det_indices:
                det = detections[i]
                
                # Only match if labels are the same
                if det['label'] != track_data['label']:
                    continue
                
                # Calculate IoU
                iou = self.calculate_iou(track_data['bbox'], det['bbox'])
                
                # Calculate center distance
                det_center = self.get_bbox_center(det['bbox'])
                track_center = track_data['center']
                distance = self.calculate_distance(track_center, det_center)
                
                # Scoring strategy:
                # - Strong match if IoU > threshold
                # - Moderate match if distance is small even with low IoU
                # - Combine both metrics for robust matching
                
                if iou > self.iou_threshold:
                    # Strong IoU match
                    score = iou + 1.0  # Bias towards IoU matches
                elif distance < self.distance_threshold:
                    # Fallback to distance-based matching
                    # Normalize distance to 0-1 range (closer = higher score)
                    normalized_distance = 1.0 - (distance / self.distance_threshold)
                    score = normalized_distance * 0.8  # Slightly lower than IoU matches
                else:
                    # No match
                    continue
                
                # Keep track of best match
                if score > best_match_score:
                    best_match_score = score
                    best_match_idx = i

            # If we found a match, update the track
            if best_match_idx != -1:
                det = detections[best_match_idx]
                
                # Update track with new detection
                self.tracked_objects[track_id]['bbox'] = det['bbox']
                self.tracked_objects[track_id]['confidence'] = det['confidence']
                self.tracked_objects[track_id]['last_seen'] = current_time
                self.tracked_objects[track_id]['center'] = self.get_bbox_center(det['bbox'])
                
                updated_track_ids.add(track_id)
                unassigned_det_indices.remove(best_match_idx)

        # Create new tracks for unassigned detections
        for i in unassigned_det_indices:
            det = detections[i]
            new_id = self.next_id
            self.next_id += 1
            
            center = self.get_bbox_center(det['bbox'])
            
            new_track = {
                'id': new_id,
                'bbox': det['bbox'],
                'label': det['label'],
                'confidence': det['confidence'],
                'last_seen': current_time,
                'center': center
            }
            
            self.tracked_objects[new_id] = new_track
            new_objects.append(new_track)
            updated_track_ids.add(new_id)

        # Remove expired tracks
        expired_ids = []
        for track_id, track_data in self.tracked_objects.items():
            if current_time - track_data['last_seen'] > self.timeout_seconds:
                expired_ids.append(track_id)
        
        for track_id in expired_ids:
            del self.tracked_objects[track_id]

        # Return active objects and new objects
        active_objects = list(self.tracked_objects.values())
        
        return active_objects, new_objects

    def calculate_iou(self, boxA, boxB):
        """Calculate Intersection over Union between two bounding boxes."""
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        # Intersection area
        interArea = max(0, xB - xA) * max(0, yB - yA)

        # Union area
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        
        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)

        return iou
    
    def get_bbox_center(self, bbox):
        """Calculate the center point of a bounding box."""
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        return (center_x, center_y)
    
    def calculate_distance(self, point1, point2):
        """Calculate Euclidean distance between two points."""
        return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def reset(self):
        """Reset the tracker, clearing all tracked objects."""
        self.tracked_objects = {}
        self.next_id = 1
