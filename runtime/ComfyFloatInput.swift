// Additive C ABI for ComfyUI. Compile with the pinned FotufilmHost sources.
// Input is straight, scene-linear Rec.2020 RGBA float32; alpha must be one.
// The normal engine, film profiles and render entry point are unchanged.
import Foundation

@_cdecl("fotufilm_image_from_rgba32f")
public func comfy_float_image(
    _ pixels: UnsafePointer<Float>?, _ width: UInt32, _ height: UInt32,
    _ count: Int, _ error: UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>?
) -> OpaquePointer? {
    let size = UInt64(width) * UInt64(height)
    guard let pixels, size > 0, size <= 40_000_000, count == Int(size) * 4 else {
        error?.pointee = strdup("Invalid float frame dimensions or buffer length.")
        return nil
    }
    let rgba = Array(UnsafeBufferPointer(start: pixels, count: count))
    guard rgba.allSatisfy({ $0.isFinite }) else {
        error?.pointee = strdup("Non-finite float source pixels.")
        return nil
    }
    let image = HostImage(rgba: rgba, width: Int(width), height: Int(height),
                          contentHeadroom: max(1, rgba.max() ?? 1))
    return OpaquePointer(Unmanaged.passRetained(image).toOpaque())
}
