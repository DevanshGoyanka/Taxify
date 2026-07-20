import org.bouncycastle.asn1.ASN1ObjectIdentifier;
import org.bouncycastle.asn1.x509.AlgorithmIdentifier;
import org.bouncycastle.cert.jcajce.JcaCertStore;
import org.bouncycastle.cms.*;
import org.bouncycastle.cms.jcajce.JcaSignerInfoGeneratorBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.DigestCalculatorProvider;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.operator.jcajce.JcaDigestCalculatorProviderBuilder;
import org.bouncycastle.util.Store;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.util.*;

/**
 * CMS Token Signer - Signs data using USB DSC token via PKCS#11
 * 
 * FIXED FOR JAVA 17+
 * Uses Provider.configure() method instead of reflection
 */
public class CMSTokenSigner {

    public static void main(String[] args) {
        if (args.length < 3) {
            System.err.println("Usage: java CMSTokenSigner <input-file> <dll-path> <pin>");
            System.exit(1);
        }

        String inputFile = args[0];
        String dllPath = args[1];
        String pin = args[2];

        try {
            // Add BouncyCastle provider
            Security.addProvider(new BouncyCastleProvider());

            // Read data to sign
            byte[] dataToSign = Files.readAllBytes(Paths.get(inputFile));
            System.err.println("Read " + dataToSign.length + " bytes from file");

            // Create PKCS11 configuration
            String pkcs11Config = String.format(
                "name=ePass2003\nlibrary=%s\n",
                dllPath
            );

            // FIXED: Use configure() method for Java 17+
            Provider pkcs11Provider = Security.getProvider("SunPKCS11");
            if (pkcs11Provider == null) {
                System.err.println("Error: SunPKCS11 provider not available");
                System.exit(1);
            }

            // Write config to temp file
            File configFile = File.createTempFile("pkcs11-", ".cfg");
            Files.write(configFile.toPath(), pkcs11Config.getBytes());
            
            // Configure provider with config file
            pkcs11Provider = pkcs11Provider.configure(configFile.getAbsolutePath());
            Security.addProvider(pkcs11Provider);
            
            // Clean up temp config file
            configFile.delete();

            // Load KeyStore
            KeyStore keyStore = KeyStore.getInstance("PKCS11", pkcs11Provider);
            keyStore.load(null, pin.toCharArray());

            // Find signing certificate
            String alias = null;
            Enumeration<String> aliases = keyStore.aliases();
            while (aliases.hasMoreElements()) {
                String a = aliases.nextElement();
                if (keyStore.isKeyEntry(a)) {
                    alias = a;
                    break;
                }
            }

            if (alias == null) {
                System.err.println("Error: No private key found in token");
                System.exit(1);
            }

            System.err.println("Using certificate alias: " + alias);

            // Get private key and certificate chain
            PrivateKey privateKey = (PrivateKey) keyStore.getKey(alias, pin.toCharArray());
            Certificate[] chain = keyStore.getCertificateChain(alias);

            if (chain == null || chain.length == 0) {
                System.err.println("Error: No certificate chain found");
                System.exit(1);
            }

            X509Certificate signerCert = (X509Certificate) chain[0];

            // Create CMS signed data
            List<X509Certificate> certList = new ArrayList<>();
            for (Certificate cert : chain) {
                certList.add((X509Certificate) cert);
            }

            Store certs = new JcaCertStore(certList);

            CMSSignedDataGenerator gen = new CMSSignedDataGenerator();

            // Use SHA256withRSA
            ContentSigner sha256Signer = new JcaContentSignerBuilder("SHA256withRSA")
                    .setProvider(pkcs11Provider)
                    .build(privateKey);

            DigestCalculatorProvider digestProvider = new JcaDigestCalculatorProviderBuilder()
                    .setProvider("BC")
                    .build();

            SignerInfoGenerator signerInfoGenerator = new JcaSignerInfoGeneratorBuilder(digestProvider)
                    .build(sha256Signer, signerCert);

            gen.addSignerInfoGenerator(signerInfoGenerator);
            gen.addCertificates(certs);

            // Generate CMS signature
            CMSTypedData cmsData = new CMSProcessableByteArray(dataToSign);
            CMSSignedData signedData = gen.generate(cmsData, false);

            byte[] signedBytes = signedData.getEncoded();

            // Output Base64 encoded signature (NO NEWLINES)
            String signature = Base64.getEncoder().encodeToString(signedBytes);
            System.out.print(signature);
            
            System.err.println("\nSignature generated successfully: " + signature.length() + " chars");

        } catch (Exception e) {
            System.err.println("Error: " + e.getClass().getName());
            e.printStackTrace(System.err);
            System.exit(1);
        }
    }
}