import subprocess, base64, json

JAVA_CLASS = "CMSTokenSigner"
BC_PROV = "bcprov-jdk18on-1.82.jar"
BC_PKIX = "bcpkix-jdk18on-1.82.jar"
BC_UTIL = "bcutil-jdk18on-1.82.jar"

PKCS11_DLL_PATH = r"C:\Windows\System32\eps2003csp11v2.dll"
TOKEN_PIN = "123456789"
ERI_USER_ID = "ERIP011535"

def generate_cms_signature(data):
    classpath = f".;{BC_PROV};{BC_PKIX};{BC_UTIL}"
    cmd = [
        "java",
        "--add-opens", "jdk.crypto.cryptoki/sun.security.pkcs11=ALL-UNNAMED",
        "-cp", classpath,
        JAVA_CLASS,
        data,
        PKCS11_DLL_PATH,
        TOKEN_PIN
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception("Java signing failed:\n" + (result.stderr or result.stdout))

    return result.stdout.strip()

def create_final_output(data):
    cms_sign = generate_cms_signature(data)
    data_b64 = base64.b64encode(data.encode("utf-8")).decode()

    output = {
        "sign": cms_sign,
        "data": data_b64,
        "eriUserId": ERI_USER_ID
    }

    print(json.dumps(output, indent=4))

if __name__ == "__main__":
    create_final_output("Hello, this is a CMS signature test!")
