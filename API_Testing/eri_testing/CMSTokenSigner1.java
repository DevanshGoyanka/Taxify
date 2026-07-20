import java.io.File;
import java.io.FileOutputStream;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.Provider;
import java.security.Security;
import java.security.cert.X509Certificate;
import java.util.Collections;
import java.util.Enumeration;

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

/**
 * Optimized minimal CMS signer (leaf-only, direct signature, detached)
 * Save as CMSTokenSigner1.java
 *
 * Note: class name remains CMSTokenSigner to match existing Python bridge.
 */
class CMSTokenSigner {

    public static String signWithToken(String data, String pkcs11LibraryPath, String pin) throws Exception {

        // Ensure BouncyCastle is available for digest calculator
        if (Security.getProvider("BC") == null) {
            Security.addProvider(new BouncyCastleProvider());
        }

        // Build temporary PKCS#11 config
        String cfg = "name=SmartCard\nlibrary=" + pkcs11LibraryPath + "\nslotListIndex=0\n";
        File configFile = File.createTempFile("pkcs11_", ".cfg");
        try (FileOutputStream fos = new FileOutputStream(configFile)) {
            fos.write(cfg.getBytes());
        }
        configFile.deleteOnExit();

        // Load SunPKCS11 provider dynamically and register
        Class<?> sunClass = Class.forName("sun.security.pkcs11.SunPKCS11");
        Provider rawProvider = (Provider) sunClass.getDeclaredConstructor().newInstance();
        Provider provider = rawProvider.configure(configFile.getAbsolutePath());
        Security.addProvider(provider);

        // Load PKCS11 KeyStore
        KeyStore ks = KeyStore.getInstance("PKCS11", provider);
        ks.load(null, pin.toCharArray());

        // Find a key entry alias
        String alias = null;
        Enumeration<String> aliases = ks.aliases();
        while (aliases.hasMoreElements()) {
            String a = aliases.nextElement();
            if (ks.isKeyEntry(a)) {
                alias = a;
                break;
            }
        }
        if (alias == null) {
            throw new Exception("No private key found on token");
        }

        // Get private key and leaf certificate (only)
        PrivateKey privateKey = (PrivateKey) ks.getKey(alias, pin.toCharArray());
        X509Certificate leafCert = (X509Certificate) ks.getCertificate(alias);

        if (privateKey == null || leafCert == null) {
            throw new Exception("Private key or certificate unavailable");
        }

        // Prepare certificate store with only leaf certificate
        Store certStore = new JcaCertStore(Collections.singletonList(leafCert));

        // Build CMS generator
        CMSSignedDataGenerator gen = new CMSSignedDataGenerator();

        // Content signer using token provider (private key remains in token)
        ContentSigner cs = new JcaContentSignerBuilder("SHA256withRSA")
                .setProvider(provider)
                .build(privateKey);

        // SignerInfo: use direct signature to minimize signed attributes
        JcaSignerInfoGeneratorBuilder sigInfoBuilder =
                new JcaSignerInfoGeneratorBuilder(
                        new JcaDigestCalculatorProviderBuilder()
                                .setProvider("BC")
                                .build()
                );
        sigInfoBuilder.setDirectSignature(true); // smaller, no extra signed attributes

        gen.addSignerInfoGenerator(sigInfoBuilder.build(cs, new X509CertificateHolder(leafCert.getEncoded())));

        // Add only leaf certificate
        gen.addCertificates(certStore);

        // Prepare content (detached = false => not embedded; use false for detached)
        CMSProcessableByteArray content = new CMSProcessableByteArray(data.getBytes("UTF-8"));
        CMSSignedData signedData = gen.generate(content, false); // detached -> false here means not encapsulated

        // Return single-line Base64 of DER bytes
        return Base64.toBase64String(signedData.getEncoded());
    }

    public static void main(String[] args) {
        if (args.length != 3) {
            System.err.println("Usage: java CMSTokenSigner <data> <pkcs11.dll path> <pin>");
            System.exit(1);
        }
        try {
            String cms = signWithToken(args[0], args[1], args[2]);
            System.out.println(cms);
        } catch (Exception ex) {
            ex.printStackTrace(System.err);
            System.exit(2);
        }
    }
}
