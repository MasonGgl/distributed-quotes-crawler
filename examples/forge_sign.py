import time,base64



def encryption_1(input):
    return base64.b64encode(f"v1|{input}|{encryption_2('salt'+str(input))}".encode()).decode()

def encryption_2(input):
    s=0
    for char in input: s = (s*31 + ord(char))%99991
    return hex(s)[2:]

if __name__ == '__main__':
    time_temp = int(time.time() * 1000)
    input_text = "1790657731747"
    print(encryption_1(input_text))
