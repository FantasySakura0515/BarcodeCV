// Configuration object for initializing the BarcodeScanner instance. Refer to https://www.dynamsoft.com/barcode-reader/docs/web/programming/javascript/api-reference/barcode-scanner.html#barcodescannerconfig
let config = {
  license: "DLS2eyJoYW5kc2hha2VDb2RlIjoiMTA1MjcyNTQwLU1UQTFNamN5TlRRd0xYZGxZaTFVY21saGJGQnliMm8iLCJtYWluU2VydmVyVVJMIjoiaHR0cHM6Ly9tZGxzLmR5bmFtc29mdG9ubGluZS5jb20vIiwib3JnYW5pemF0aW9uSUQiOiIxMDUyNzI1NDAiLCJzdGFuZGJ5U2VydmVyVVJMIjoiaHR0cHM6Ly9zZGxzLmR5bmFtc29mdG9ubGluZS5jb20vIiwiY2hlY2tDb2RlIjo3OTQ1MDUxMjZ9", // Replace with your Dynamsoft license key
  container: document.querySelector(".barcode-scanner-view"), // Specify where to render the scanner UI

  // showUploadImageButton: true,
  // scannerViewConfig: {
  //   showFlashButton: true,
  //   cameraSwitchControl: "toggleFrontBack",
  // },
};

// Create a new instance of the Dynamsoft Barcode Scanner
const barcodeScanner = new Dynamsoft.BarcodeScanner(config);

// Launch the scanner and handle the scanned result
barcodeScanner.launch().then((result) => {
  // Display the first detected barcode's text in an alert
  if (result.barcodeResults.length) {
    alert(result.barcodeResults[0].text);
  }
});