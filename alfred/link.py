import sys
import subprocess


query = sys.argv[1]


def write_to_clipboard(output):
    process = subprocess.Popen(
        'pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
    process.communicate(output.encode('utf-8'))


output = query.replace('https://', '').replace('http://', '').replace('', '')

write_to_clipboard(output)

print(output)