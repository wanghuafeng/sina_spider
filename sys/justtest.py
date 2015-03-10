import glob
import os
path = os.path.dirname(__file__)
file_pattern =os.path.join(path, 'html', '*.html')
print file_pattern
print glob.glob(file_pattern)