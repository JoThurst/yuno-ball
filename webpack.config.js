const path = require('path');
const fs = require('fs');

module.exports = {
    mode: 'production',
    entry: {
        charts: './app/static/js/charts.js',
        aos: './app/static/js/aos-bundle.js',
        swiper: './app/static/js/swiper-bundle.js',
        main: './app/static/js/main.js'
    },
    output: {
        filename: '[name].bundle.js',
        path: path.resolve(__dirname, 'app/static/dist'),
        clean: true
    },
    module: {
        rules: [
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader']
            }
        ]
    },
    optimization: {
        minimize: true
    }
};

// Create bundle files if they don't exist
const bundleDir = path.resolve(__dirname, 'app/static/js');
if (!fs.existsSync(bundleDir)) {
    fs.mkdirSync(bundleDir, { recursive: true });
}

// Create AOS bundle
const aosBundle = path.join(bundleDir, 'aos-bundle.js');
if (!fs.existsSync(aosBundle)) {
    fs.writeFileSync(aosBundle, `
        import AOS from 'aos';
        import 'aos/dist/aos.css';
        export default AOS;
        window.AOS = AOS;
    `);
}

// Create Swiper bundle
const swiperBundle = path.join(bundleDir, 'swiper-bundle.js');
if (!fs.existsSync(swiperBundle)) {
    fs.writeFileSync(swiperBundle, `
        import Swiper from 'swiper';
        import { Navigation, Pagination, Autoplay } from 'swiper/modules';
        import 'swiper/css';
        import 'swiper/css/navigation';
        import 'swiper/css/pagination';
        export default Swiper;
        window.Swiper = Swiper;
    `);
} 