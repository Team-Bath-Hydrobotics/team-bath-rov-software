import cv2

def brightness_filter(frame, delta=30):
    return cv2.convertScaleAbs(frame, alpha=1, beta=delta)


def lowpass_filter(frame, ksize=5):
    ksize = ksize if ksize % 2 else ksize + 1
    return cv2.GaussianBlur(frame, (ksize, ksize), 0)


def resize_filter(frame, scale=0.5):
    h, w = frame.shape[:2]
    return cv2.resize(frame, (int(w * scale), int(h * scale)))


def greyscale_filter(frame, _=None):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


# Boosts visibility in dark water environments
def contrast_filter(frame, alpha=1.5):
    return cv2.convertScaleAbs(frame, alpha=alpha, beta=0)


# register filters
FILTERS = {
    "brightness": brightness_filter,
    "lowpass": lowpass_filter,
    "resize": resize_filter,
    "contrast": contrast_filter,
    "greyscale": greyscale_filter,
}
