package com.hefatss.re6rr;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Resolves the executable's `sim:` paths and inflates gzip containers.
 *
 *  On Android the root is a game dump; the native bridge owns inflation via
 *  Re6Engine::inflateGzip. The default inflater uses java.util.zip so this
 *  class stays testable on a desktop JDK.
 */
public final class AssetProvider {
    /** Byte-level gzip inflation; the engine bridge implements this natively. */
    @FunctionalInterface
    public interface Inflater {
        byte[] inflate(byte[] compressed);
    }

    private final Path root;
    private final Inflater inflater;

    public AssetProvider(String root) {
        this(root, AssetProvider::javaInflate);
    }

    public AssetProvider(String root, Inflater inflater) {
        this.root = Paths.get(root);
        this.inflater = inflater;
    }

    /** Accepts "sim:data/...", "data/..." or an absolute path. */
    public Path resolve(String path) {
        String clean = path.startsWith("sim:") ? path.substring(4) : path;
        Path candidate = Paths.get(clean);
        return candidate.isAbsolute() ? candidate : root.resolve(candidate);
    }

    /** Read a file and inflate it when it is a gzip member. */
    public byte[] read(String path) throws IOException {
        byte[] raw = Files.readAllBytes(resolve(path));
        if (raw.length >= 3 && (raw[0] & 0xff) == 0x1f &&
            (raw[1] & 0xff) == 0x8b && (raw[2] & 0xff) == 0x08) {
            byte[] inflated = inflater.inflate(raw);
            if (inflated == null) {
                throw new IOException("gzip inflate failed: " + path);
            }
            return inflated;
        }
        return raw;
    }

    /** Ordered script templates recovered from the executable loaders.
     *  Mirrors tools/engine/contexts.py; missing files are skipped.
     */
    public List<String> carScripts(String car, String model) {
        if (model == null || model.isEmpty()) {
            model = car;
        }
        List<String> paths = new ArrayList<>();
        add(paths, "data/car/tire/script/TireDefine.lua");
        add(paths, "data/car/tire/model_type/TireModelType_%s.lua", car);
        add(paths, "data/car/tire/script/TireAccessor.lua");
        add(paths, "data/car/position/pos/getTirePos_%s.lua", car);
        add(paths, "data/car/position/hightDown/CarHightDown_%s.lua", model);
        add(paths, "data/car/position/StroboLightOnOffParameter.lua");
        add(paths, "data/car/shader/parameter/%s_ShaderParameter.lua", model);
        add(paths, "data/car/shader/script/ShaderAccessor.lua");
        add(paths, "data/car/specification/%s_Specification.lua", model);
        add(paths, "data/car/color/LibraryColor.lua");
        add(paths, "data/car/color/ColorCommonParamerter.lua");
        add(paths, "data/car/color/NeonColor.lua");
        return paths;
    }

    private void add(List<String> out, String template, Object... args) {
        String relative = String.format(template, args);
        if (Files.isRegularFile(resolve(relative))) {
            out.add(relative);
        }
    }

    private static byte[] javaInflate(byte[] compressed) {
        try (java.util.zip.GZIPInputStream in = new java.util.zip.GZIPInputStream(
                 new java.io.ByteArrayInputStream(compressed))) {
            return in.readAllBytes();
        } catch (IOException e) {
            return null;
        }
    }

    /** Convenience: load a context bundle into an engine. */
    public int loadCar(Re6Engine engine, String car, String model)
            throws IOException {
        List<String> paths = carScripts(car, model);
        String[] names = new String[paths.size()];
        byte[][] chunks = new byte[paths.size()][];
        for (int i = 0; i < paths.size(); i++) {
            names[i] = paths.get(i);
            chunks[i] = read(paths.get(i));
        }
        return engine.loadContext(names, chunks);
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: AssetProvider <dump dir>");
            System.exit(2);
        }
        AssetProvider assets = new AssetProvider(args[0]);
        int scripts = assets.carScripts("CRC_928GT_Masaki", "PLC_928GT").size();
        byte[] tex = assets.read("sim:data/car/car_data/charCar/"
                                 + "CRC_928GT_Masaki/CRC_928GT_Masaki.tex");
        String tag = new String(Arrays.copyOf(tex, 7), java.nio.charset.StandardCharsets.ISO_8859_1);
        System.out.println("scripts=" + scripts);
        System.out.println("tex=" + tex.length + " tag=" + tag);
        if (scripts != 12 || tex.length < 200000 || !tag.startsWith("XMD")) {
            throw new AssertionError("asset provider mismatch");
        }
    }
}
