const path = require("path");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

const autoPrefixerOptions = {
  overrideBrowserslist: ["last 2 versions"],
};

module.exports = {
  mode: "development",
  entry: "./src/hyperadmin/static/js/index.js",
  module: {
    rules: [
      {
        test: /\.m?js$/,
        exclude: /node_modules/,
        use: {
          loader: "babel-loader",
          options: {
            presets: ["@babel/preset-env"],
          },
        },
      },
      {
        test: /\.css$/i,
        use: [
          MiniCssExtractPlugin.loader,
          "css-loader",
          {
            loader: "postcss-loader",
            options: {
              postcssOptions: {
                plugins: [
                  require("autoprefixer")(autoPrefixerOptions),
                ],
              },
            },
          },
        ],
      },
      {
        test: /\.(png|svg|jpg|jpeg|gif)$/i,
        type: "asset/resource",
        generator: {
            filename: '../images/[name][ext]'
        }
      },
      {
        test: /\.(woff|woff2|eot|ttf|otf)$/i,
        type: "asset/resource",
        generator: {
            filename: '../fonts/[name][ext]'
        }
      },
    ],
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: "../css/output.css",
    }),
  ],
  output: {
    filename: "main.js",
    path: path.resolve(__dirname, "src/hyperadmin/static/dist"),
    clean: true,
  },
  target: "web", // fix for "browserslist" error message
  stats: "errors-only", // suppress irrelevant log messages
};