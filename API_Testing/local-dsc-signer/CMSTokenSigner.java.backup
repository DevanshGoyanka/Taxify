/**
 * CMSTokenSigner.java - ITD Compliant CMS Signer for HyperPKI / ePass Tokens
 * Save as: C:\Users\Devansh\Desktop\eri_testing\CMSTokenSigner.java
 * Fully compatible with Java 8—25.
 */

import java.io.File;
import java.io.FileOutputStream;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.Provider;
import java.security.Security;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;

import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.CMSSignedDataGenerator;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;
import org.bouncycastle.util.Store;
import org.bouncycastle.util.encoders.Base64;

public class CMSTokenSigner {

    public static String signWithToken(String data, String pkcs11LibraryPath, String pin) throws Exception {

        // Add BouncyCastle provider
        Security.addProvider(new BouncyCastleProvider());

        System.err.println("======================================================================");
        System.err.println("CMS Token Signer - ITD Compliant");
        System.err.println("======================================================================");
        System.err.println("PKCS#11 Library: " + pkcs11LibraryPath);
        System.err.println("Data length: " + data.length() + " chars");

        // Detect Java version and architecture
        String javaVersion = System.getProperty("java.version");
        String javaArch = System.getProperty("sun.arch.data.model");
        System.err.println("Detected Java version: " + javaVersion);
        System.err.println("Java architecture: " + javaArch + "-bit");

        // Check if DLL path exists
        File dllFile = new File(pkcs11LibraryPath);
        if (!dllFile.exists()) {
            System.err.println("✗ WARNING: DLL file not found at specified path!");
            System.err.println("  Please verify the path exists.");
        } else {
            System.err.println("✓ DLL file found");
        }

        // Build PKCS#11 configuration
        String pkcs11Config =
            "name = SmartCard\n" +
            "library = " + pkcs11LibraryPath + "\n" +
            "slotListIndex = 0\n";

        // Create temporary config file (required for Java 9+)
        File configFile = File.createTempFile("pkcs11", ".cfg");
        try (FileOutputStream fos = new FileOutputStream(configFile)) {
            fos.write(pkcs11Config.getBytes());
        }
        configFile.deleteOnExit();
        
        System.err.println("✓ Config file created: " + configFile.getAbsolutePath());

        // Load PKCS#11 provider using direct instantiation
        Provider pkcs11Provider = null;
        
        try {
            System.err.println("→ Loading PKCS#11 provider for Java 9+...");
            
            // For Java 9+, use Provider.configure() method
            // First get the base SunPKCS11 provider class
            Class<?> sunPkcs11Class = Class.forName("sun.security.pkcs11.SunPKCS11");
            
            // Create instance with no-arg constructor
            pkcs11Provider = (Provider) sunPkcs11Class.getDeclaredConstructor().newInstance();
            
            // Configure it with the config file path
            pkcs11Provider = pkcs11Provider.configure(configFile.getAbsolutePath());
            
            System.err.println("✓ PKCS#11 Provider created successfully");
            
        } catch (Exception e) {
            System.err.println("✗ Failed to load PKCS#11 provider: " + e.getMessage());
            System.err.println("\nPossible issues:");
            System.err.println("  1. Java architecture mismatch: You're running " + javaArch + "-bit Java");
            System.err.println("     - 32-bit DLL requires 32-bit Java");
            System.err.println("     - 64-bit DLL requires 64-bit Java");
            System.err.println("  2. USB token not inserted or not recognized");
            System.err.println("  3. Token drivers not properly installed");
            System.err.println("  4. Incorrect DLL path");
            System.err.println("\nFor 64-bit Java, try:");
            System.err.println("  C:\\Windows\\System32\\eToken.dll");
            System.err.println("  C:\\Program Files\\HyperSecu\\HyperPKI\\HyperPKICsp11_2003.dll");
            throw e;
        }

        // Add provider to security
        if (Security.addProvider(pkcs11Provider) == -1) {
            System.err.println("✗ Failed to add provider to Security");
            throw new Exception("Failed to register PKCS#11 provider");
        }
        
        System.err.println("✓ Provider registered: " + pkcs11Provider.getName());

        // Load keystore from token
        // For SunPKCS11, the KeyStore is accessed through the provider's KeyStore.Builder
        // Or we can use the default type which the provider exposes
        KeyStore keyStore;
        try {
            // Try to get KeyStore using the provider's default type
            keyStore = KeyStore.getInstance("PKCS11");
        } catch (Exception e1) {
            // If that fails, the provider might use a different name
            // Try getting the first KeyStore type from the provider
            System.err.println("→ PKCS11 type not found, trying provider's KeyStore types...");
            String ksType = null;
            for (Provider.Service service : pkcs11Provider.getServices()) {
                if ("KeyStore".equals(service.getType())) {
                    ksType = service.getAlgorithm();
                    System.err.println("  Found KeyStore type: " + ksType);
                    break;
                }
            }
            if (ksType != null) {
                keyStore = KeyStore.getInstance(ksType, pkcs11Provider);
            } else {
                throw new Exception("No KeyStore type found in provider. Token may not be inserted or drivers not working.");
            }
        }
        System.err.println("✓ KeyStore instance created");
        System.err.println("✓ Loading keystore from USB token...");
        
        try {
            keyStore.load(null, pin.toCharArray());
            System.err.println("✓ Keystore loaded successfully");
        } catch (Exception e) {
            System.err.println("✗ Failed to load keystore: " + e.getMessage());
            System.err.println("\nPossible issues:");
            System.err.println("  1. Incorrect PIN");
            System.err.println("  2. USB token not inserted");
            System.err.println("  3. Token is locked (too many wrong PIN attempts)");
            System.err.println("  4. Architecture mismatch between Java and DLL");
            throw e;
        }

        // Get certificate alias - find one with a private key
        Enumeration<String> aliases = keyStore.aliases();
        if (!aliases.hasMoreElements()) {
            throw new Exception("No certificates found in token");
        }

        String alias = null;
        System.err.println("→ Searching for certificate with private key...");
        while (aliases.hasMoreElements()) {
            String currentAlias = aliases.nextElement();
            if (keyStore.isKeyEntry(currentAlias)) {
                alias = currentAlias;
                System.err.println("✓ Found key entry: " + currentAlias);
                break;
            } else {
                System.err.println("  Skipping (no key): " + currentAlias);
            }
        }
        
        if (alias == null) {
            throw new Exception("No private key entry found in token");
        }
        
        System.err.println("✓ Using certificate alias: " + alias);

        // Get certificate chain (or single certificate)
        Certificate[] certChain = keyStore.getCertificateChain(alias);
        
        // If chain is null, try getting single certificate
        if (certChain == null || certChain.length == 0) {
            System.err.println("→ Certificate chain not found, trying single certificate...");
            Certificate cert = keyStore.getCertificate(alias);
            if (cert == null) {
                throw new Exception("No certificate found for alias: " + alias);
            }
            certChain = new Certificate[] { cert };
            System.err.println("✓ Using single certificate (no chain)");
        } else {
            System.err.println("✓ Certificate chain length: " + certChain.length);
        }

        List<Certificate> certList = new ArrayList<>();
        for (Certificate cert : certChain) {
            certList.add(cert);
            if (cert instanceof X509Certificate) {
                X509Certificate x509 = (X509Certificate) cert;
                System.err.println("  - Subject: " + x509.getSubjectDN().getName());
            }
        }

        // Get private key (stays in token)
        PrivateKey privateKey = (PrivateKey) keyStore.getKey(alias, pin.toCharArray());
        if (privateKey == null) {
            throw new Exception("Private key not accessible");
        }

        System.err.println("✓ Private key accessible (stays in token)");

        X509Certificate certificate = (X509Certificate) certChain[0];
        Store certStore = new JcaCertStore(certList);

        // Create CMS signed data generator
        CMSSignedDataGenerator cmsGenerator = new CMSSignedDataGenerator();

        // Create content signer using token
        System.err.println("✓ Creating CMS signature...");
        ContentSigner sha256Signer = new JcaContentSignerBuilder("SHA256withRSA")
            .setProvider(pkcs11Provider)
            .build(privateKey);

        X509CertificateHolder certHolder = new X509CertificateHolder(certificate.getEncoded());
        cmsGenerator.addSignerInfoGenerator(
            new JcaSignerInfoGeneratorBuilder(
                new JcaDigestCalculatorProviderBuilder()
                    .setProvider("BC")
                    .build()
            ).build(sha256Signer, certHolder)
        );

        cmsGenerator.addCertificates(certStore);

        // Generate CMS signature
        CMSProcessableByteArray cmsData = new CMSProcessableByteArray(data.getBytes("UTF-8"));
        CMSSignedData signedData = cmsGenerator.generate(cmsData, false);

        byte[] signedBytes = signedData.getEncoded();
        String signature = Base64.toBase64String(signedBytes);

        System.err.println("✓ CMS signature generated!");
        System.err.println("  Signature length: " + signature.length() + " characters");
        System.err.println("======================================================================");

        return signature;
    }

    public static void main(String[] args) {
        if (args.length < 3) {
            System.err.println("Usage: java CMSTokenSigner <data> <pkcs11_dll_path> <pin>");
            System.err.println("\nExamples:");
            System.err.println("  For 64-bit Java:");
            System.err.println("    java CMSTokenSigner \"test\" \"C:\\\\Program Files\\\\HyperSecu\\\\HyperPKI\\\\HyperPKICsp11_2003.dll\" \"12345678\"");
            System.err.println("  For 32-bit Java:");
            System.err.println("    java CMSTokenSigner \"test\" \"C:\\\\Program Files (x86)\\\\Hypersecu\\\\HyperPKI\\\\HyperPKICsp11_2003.dll\" \"12345678\"");
            System.exit(1);
        }

        String data = args[0];
        String pkcs11Path = args[1];
        String pin = args[2];

        try {
            String signature = signWithToken(data, pkcs11Path, pin);
            System.out.println(signature);
            System.err.println("\n✓✓✓ SUCCESS ✓✓✓");

        } catch (Exception e) {
            System.err.println("\n✗✗✗ ERROR ✗✗✗");
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace(System.err);
            System.exit(1);
        }
    }
}