import cv2

class Filter:
    def __init__(self, filter_funcs: list[str], **kwargs):
        self.filter_funcs = filter_funcs
        self.params = kwargs

    def apply(self, frame):
        if self.filter_funcs is None or len(self.filter_funcs) == 0:
            return frame
        
        for filter_func in self.filter_funcs:
            if filter_func == "brightness":
                frame = self.brightness_filter(frame, **self.params)
            elif filter_func == "lowpass":
                frame = self.lowpass_filter(frame, **self.params)
            elif filter_func == "resize":
                frame = self.resize_filter(frame, **self.params)
            elif filter_func == "greyscale":
                frame = self.greyscale_filter(frame, **self.params)
            elif filter_func == "contrast":
                frame = self.contrast_filter(frame, **self.params)

        return frame
    
    def brightness_filter(self, frame, delta=30):
        return cv2.convertScaleAbs(frame, alpha=1, beta=delta)

    def lowpass_filter(self, frame, ksize=5):
        ksize = ksize if ksize % 2 else ksize + 1
        return cv2.GaussianBlur(frame, (ksize, ksize), 0)

    def resize_filter(self, frame, scale=0.5):
        h, w = frame.shape[:2]
        return cv2.resize(frame, (int(w * scale), int(h * scale)))

    def greyscale_filter(self, frame, _=None):
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Boosts visibility in dark water environments
    def contrast_filter(self, frame, alpha=1.5):
        return cv2.convertScaleAbs(frame, alpha=alpha, beta=0)