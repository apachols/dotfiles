import subprocess
import datetime


def write_to_clipboard(output):
    process = subprocess.Popen(
        'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
    process.communicate(output.encode('utf-8'))


strdate = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')

write_to_clipboard(strdate)
