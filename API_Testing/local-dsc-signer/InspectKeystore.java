import java.security.KeyStore;
import java.security.cert.X509Certificate;
import java.util.Enumeration;

public class InspectKeystore {
    public static void main(String[] args) {
        try {
            KeyStore keyStore = KeyStore.getInstance("Windows-MY");
            keyStore.load(null, null);
            Enumeration<String> aliases = keyStore.aliases();
            System.out.println("--- KEYSTORE ALIASES ---");
            while (aliases.hasMoreElements()) {
                String alias = aliases.nextElement();
                System.out.println("Alias: " + alias);
                System.out.println("  isKeyEntry: " + keyStore.isKeyEntry(alias));
                
                X509Certificate cert = (X509Certificate) keyStore.getCertificate(alias);
                if (cert != null) {
                    System.out.println("  Subject: " + cert.getSubjectX500Principal().getName());
                    System.out.println("  Issuer: " + cert.getIssuerX500Principal().getName());
                    System.out.println("  Valid From: " + cert.getNotBefore());
                    System.out.println("  Valid Until: " + cert.getNotAfter());
                    
                    try {
                        cert.checkValidity();
                        System.out.println("  checkValidity(): VALID");
                    } catch (Exception e) {
                        System.out.println("  checkValidity(): INVALID (" + e.getMessage() + ")");
                    }
                    
                    boolean[] keyUsage = cert.getKeyUsage();
                    if (keyUsage != null) {
                        System.out.print("  Key Usage: ");
                        for (int i = 0; i < keyUsage.length; i++) {
                            System.out.print(keyUsage[i] + " ");
                        }
                        System.out.println();
                    } else {
                        System.out.println("  Key Usage: null");
                    }
                }
                System.out.println();
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
