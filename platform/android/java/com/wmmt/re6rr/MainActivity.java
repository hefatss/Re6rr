package com.wmmt.re6rr;

import android.app.Activity;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.ToggleButton;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

/** Headless host: loads the dumped Lua context and drives the freestanding
 *  race loop. No renderer yet; telemetry is shown as text.
 *
 *  Put generated cars.r6car and *.r6course in
 *  /sdcard/Android/data/com.wmmt.re6rr/files/dump/ along with the data/ tree.
 */
public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private File root;
    private EditText pathField;
    private EditText characterField;
    private Spinner carSpinner;
    private Spinner courseSpinner;
    private ToggleButton driveButton;
    private SeekBar steerBar;
    private TextView status;

    private Re6Engine engine;
    private Re6Engine.Game game;
    private Re6Engine.Vehicle vehicle;
    private Re6Engine.Race race;
    private Re6Engine.CarCatalog catalog;
    private Re6Engine.CustomCatalog custom;
    private Re6Engine.StoryCatalog story;
    private byte[] descriptor;
    private List<String> models = new ArrayList<>();
    private List<String> courses = new ArrayList<>();
    private boolean running;
    private float steer;

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            if (!running) {
                return;
            }
            int rc = race.step(descriptor, vehicle.state(), 1.0f / 60.0f);
            float[] state = race.state();
            int surface = state.length > 18 ? (int)state[18] : 0;
            int outcome = state.length > 1 ? (int)state[1] : 0;
            float elapsed = state.length > 2 ? state[2] : 0.0f;
            vehicle.setSurface(surface);
            float speed = vehicle.state()[14];
            int gear = speed > 60.0f ? 5 : speed > 40.0f ? 4 :
                       speed > 25.0f ? 3 : speed > 12.0f ? 2 : 1;
            boolean drive = driveButton.isChecked();
            vehicle.step(drive ? 1.0f : 0.0f, drive ? 0.0f : 1.0f,
                         steer, gear, 1.0f / 60.0f);
            game.step(outcome, elapsed, 1.0f / 60.0f);
            status.setText(String.format(
                    "phase=%d rc=%d odo=%.1f speed=%.1f gear=%d surface=%d " +
                    "offroad=%d lap=%d place=%d",
                    game.phase(), rc, state[10], speed, gear, surface,
                    (int)state[19], (int)state[4], (int)state[22]));
            handler.postDelayed(this, 16);
        }
    };

    @Override
    protected void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        File fallback = getExternalFilesDir(null);
        root = new File(fallback != null ? fallback : getFilesDir(), "dump");
        if (!root.isDirectory()) {
            root = fallback != null ? fallback : getFilesDir();
        }

        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        int pad = 16;
        view.setPadding(pad, pad, pad, pad);

        pathField = field("dump directory: " + root.getAbsolutePath());
        characterField = field("character car (optional, e.g. CRC_928GT_Masaki)");
        carSpinner = new Spinner(this);
        courseSpinner = new Spinner(this);

        driveButton = new ToggleButton(this);
        driveButton.setTextOn("throttle on");
        driveButton.setTextOff("throttle off");
        driveButton.setChecked(true);

        steerBar = new SeekBar(this);
        steerBar.setMax(200);
        steerBar.setProgress(100);
        steerBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar bar, int progress, boolean fromUser) {
                steer = (progress - 100) / 100.0f;
            }

            @Override
            public void onStartTrackingTouch(SeekBar bar) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar bar) {
            }
        });

        Button reload = new Button(this);
        reload.setText("reload assets");
        reload.setOnClickListener(v -> loadAssets());

        Button start = new Button(this);
        start.setText("start race");
        start.setOnClickListener(v -> startRace());

        Button stop = new Button(this);
        stop.setText("stop");
        stop.setOnClickListener(v -> stopRace());

        status = new TextView(this);
        status.setText("ready");

        view.addView(pathField);
        view.addView(characterField);
        view.addView(label("car model"));
        view.addView(carSpinner);
        view.addView(label("course descriptor"));
        view.addView(courseSpinner);
        view.addView(label("steer"));
        view.addView(steerBar);
        view.addView(driveButton);
        view.addView(reload);
        view.addView(start);
        view.addView(stop);
        view.addView(status);
        setContentView(view);
        loadAssets();
    }

    private EditText field(String hint) {
        EditText result = new EditText(this);
        result.setHint(hint);
        result.setSingleLine(true);
        return result;
    }

    private TextView label(String text) {
        TextView result = new TextView(this);
        result.setText(text);
        return result;
    }

    private void loadAssets() {
        stopRace();
        String path = pathField.getText().toString().trim();
        root = path.isEmpty() ? getExternalFilesDir(null) : new File(path);
        if (root == null) {
            root = getFilesDir();
        }
        try {
            byte[] blob = Files.readAllBytes(new File(root, "cars.r6car").toPath());
            catalog = new Re6Engine.CarCatalog(blob);
            models.clear();
            for (int i = 0; i < catalog.count(); i++) {
                byte[] model = catalog.model(i);
                models.add(new String(model == null ? new byte[0] : model,
                                      StandardCharsets.US_ASCII));
            }
            carSpinner.setAdapter(adapter(models));

            custom = null;
            File customFile = new File(root, "custom.r6custom");
            String customText = "";
            if (customFile.isFile()) {
                custom = new Re6Engine.CustomCatalog(
                        Files.readAllBytes(customFile.toPath()));
                customText = " colours=" + custom.count(0) +
                             " wheels=" + custom.count(1);
            }

            story = null;
            File storyFile = new File(root, "story.r6story");
            String storyText = "";
            if (storyFile.isFile()) {
                story = new Re6Engine.StoryCatalog(
                        Files.readAllBytes(storyFile.toPath()));
                storyText = " episodes=" + story.count(0);
            }

            courses.clear();
            File[] files = root.listFiles((dir, name) -> name.endsWith(".r6course"));
            if (files != null) {
                Arrays.sort(files, Comparator.comparing(File::getName));
                for (File file : files) {
                    courses.add(file.getName());
                }
            }
            courseSpinner.setAdapter(adapter(courses));
            status.setText("cars=" + models.size() + " courses=" + courses.size() +
                           " characters=" + catalog.characterCount() +
                           customText + storyText);
        } catch (Exception error) {
            status.setText("load failed: " + error);
        }
    }

    private ArrayAdapter<String> adapter(List<String> values) {
        ArrayAdapter<String> result = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, values);
        result.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        return result;
    }

    private void startRace() {
        stopRace();
        try {
            if (catalog == null || models.isEmpty() || courses.isEmpty()) {
                throw new IOException("load assets first");
            }
            String character = characterField.getText().toString().trim();
            String carName;
            String modelName;
            int carIndex;
            if (!character.isEmpty()) {
                carIndex = catalog.carIndexForCharacter(character);
                if (carIndex < 0) {
                    throw new IOException("unmapped character: " + character);
                }
                byte[] model = catalog.model(carIndex);
                carName = character;
                modelName = new String(model, StandardCharsets.US_ASCII);
            } else {
                carIndex = carSpinner.getSelectedItemPosition();
                modelName = models.get(carIndex);
                carName = modelName;
            }
            int courseIndex = courseSpinner.getSelectedItemPosition();
            File courseFile = new File(root, courses.get(courseIndex));
            descriptor = Files.readAllBytes(courseFile.toPath());

            engine = new Re6Engine();
            AssetProvider assets = new AssetProvider(
                    root.getAbsolutePath(), Re6Engine::inflateGzip);
            assets.loadCar(engine, carName, modelName);
            vehicle = engine.createVehicle(carName, modelName);
            game = Re6Engine.Game.create();
            game.selectCar(carIndex);
            game.selectCourse(courseIndex, 0, 3);
            game.start();
            race = engine.createRace(4, 3, courseIndex, 0, 1.0e8f, 0.0f,
                                     3.0f, 1, 2.0f, 1.0f);
            running = true;
            handler.post(tick);
        } catch (Exception error) {
            status.setText("start failed: " + error);
            stopRace();
        }
    }

    private void stopRace() {
        running = false;
        handler.removeCallbacks(tick);
        close(race);
        close(vehicle);
        close(game);
        close(engine);
        race = null;
        vehicle = null;
        game = null;
        engine = null;
        descriptor = null;
    }

    private static void close(AutoCloseable value) {
        if (value == null) {
            return;
        }
        try {
            value.close();
        } catch (Exception ignored) {
            // Nothing useful to do while tearing down a race.
        }
    }

    @Override
    protected void onDestroy() {
        stopRace();
        super.onDestroy();
    }
}
