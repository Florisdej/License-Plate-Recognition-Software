   from ultralytics import YOLO
   model = YOLO("models/best.pt")
   results = model('/Users/florisdejager/Downloads/Data Fietspaden Nederland/DSC00202.jpg')
   res = results[0]

   print("Boxes tensor:", res.boxes)
   print("OBB tensor:", getattr(res, "obb", None))