# No trained AutoML weights
The pilot was prepared but not run because GPU quota was blocked. No selected model,
no download, no accuracy, no invented weights. Native AutoMode5trials/1concurrent/90minutes,
10train/3validation/9evaluation. train.py prepares privately; --submit requires fresh approval,
quota plus verified private upload. [download_best.py](../download_best.py) can acquire only a
completed validation-selected model after fresh authorization; it never selects using evaluation.
test.py --contracts checks the native payload offline; --image requires a real selected MLflow
model and its matching selection receipt. No anonymous results should claim a score.
