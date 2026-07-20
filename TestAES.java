import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.util.Base64;

public class TestAES {
    public static void main(String[] args) throws Exception {
        String symmetricKeyB64 = "Xuslp8BPWDe0QCF+rLCGZA==";
        String password = "Oracle@123";

        byte[] key = Base64.getDecoder().decode(symmetricKeyB64);
        SecretKeySpec secretKey = new SecretKeySpec(key, "AES");
        
        Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
        cipher.init(Cipher.ENCRYPT_MODE, secretKey);
        
        byte[] encrypted = cipher.doFinal(password.getBytes("UTF-8"));
        System.out.println("Java Encrypted: " + Base64.getEncoder().encodeToString(encrypted));
    }
}
